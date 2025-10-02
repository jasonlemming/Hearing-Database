"""
Base parser class for data validation and transformation
"""
from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, ValidationError

from config.logging_config import get_logger

logger = get_logger(__name__)


class BaseParser(ABC):
    """Base class for data parsers with validation"""

    def __init__(self, strict_mode: bool = False):
        """
        Initialize parser

        Args:
            strict_mode: If True, validation errors halt processing
        """
        self.strict_mode = strict_mode
        self.errors: List[Dict[str, Any]] = []

    @abstractmethod
    def parse(self, raw_data: Dict[str, Any]) -> Optional[BaseModel]:
        """
        Parse raw API data into validated model

        Args:
            raw_data: Raw data from API

        Returns:
            Validated model instance or None if parsing failed
        """
        pass

    def validate_required_fields(self, data: Dict[str, Any], required: List[str]) -> bool:
        """
        Validate that required fields are present

        Args:
            data: Data dictionary to validate
            required: List of required field names

        Returns:
            True if all required fields present
        """
        missing = []
        for field in required:
            if not self._has_value(data, field):
                missing.append(field)

        if missing:
            error_msg = f"Missing required fields: {missing}"
            self.collect_error('validation', error_msg, 'critical' if self.strict_mode else 'warning')
            return False

        return True

    def _has_value(self, data: Dict[str, Any], field: str) -> bool:
        """Check if field has a non-empty value"""
        if '.' in field:
            # Handle nested fields
            keys = field.split('.')
            current = data
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return False
            return current is not None and str(current).strip() != ''
        else:
            value = data.get(field)
            return value is not None and str(value).strip() != ''

    def normalize_date(self, date_string: str) -> Optional[date]:
        """
        Normalize date string to date object

        Args:
            date_string: Date string in various formats

        Returns:
            Date object or None if parsing failed
        """
        if not date_string:
            return None

        # Common date formats from Congress.gov API
        date_formats = [
            '%Y-%m-%d',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%m/%d/%Y',
            '%m-%d-%Y'
        ]

        for fmt in date_formats:
            try:
                parsed = datetime.strptime(date_string, fmt)
                return parsed.date()
            except ValueError:
                continue

        self.collect_error('parse_error', f"Could not parse date: {date_string}", 'warning')
        return None

    def normalize_datetime(self, datetime_string: str) -> Optional[datetime]:
        """
        Normalize datetime string to datetime object

        Args:
            datetime_string: Datetime string in various formats

        Returns:
            Datetime object or None if parsing failed
        """
        if not datetime_string:
            return None

        # Common datetime formats
        datetime_formats = [
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d'
        ]

        for fmt in datetime_formats:
            try:
                return datetime.strptime(datetime_string, fmt)
            except ValueError:
                continue

        self.collect_error('parse_error', f"Could not parse datetime: {datetime_string}", 'warning')
        return None

    def normalize_text(self, text: str) -> str:
        """
        Normalize text field (trim, clean)

        Args:
            text: Raw text

        Returns:
            Normalized text
        """
        if not text:
            return ""

        # Clean up common issues
        normalized = str(text).strip()
        # Remove multiple spaces
        normalized = ' '.join(normalized.split())
        return normalized

    def normalize_integer(self, value: Any) -> Optional[int]:
        """
        Normalize value to integer

        Args:
            value: Value to convert

        Returns:
            Integer value or None
        """
        if value is None:
            return None

        try:
            if isinstance(value, str):
                # Handle comma-separated numbers
                value = value.replace(',', '')
            return int(float(value))
        except (ValueError, TypeError):
            self.collect_error('parse_error', f"Could not parse integer: {value}", 'warning')
            return None

    def safe_get(self, data: Dict[str, Any], key: str, default: Any = None) -> Any:
        """
        Safely get value from nested dictionary

        Args:
            data: Dictionary to search
            key: Key to find (supports dot notation)
            default: Default value

        Returns:
            Value or default
        """
        if '.' in key:
            keys = key.split('.')
            current = data
            for k in keys:
                if isinstance(current, dict) and k in current:
                    current = current[k]
                else:
                    return default
            return current
        else:
            return data.get(key, default)

    def collect_error(self, error_type: str, message: str, severity: str = 'warning') -> None:
        """
        Collect parsing error

        Args:
            error_type: Type of error (validation, parse_error, etc.)
            message: Error message
            severity: Error severity (critical, warning)
        """
        error = {
            'error_type': error_type,
            'message': message,
            'severity': severity,
            'timestamp': datetime.now()
        }
        self.errors.append(error)

        if severity == 'critical':
            logger.error(f"Critical parsing error: {message}")
        else:
            logger.warning(f"Parsing warning: {message}")

    def get_errors(self) -> List[Dict[str, Any]]:
        """Get collected errors"""
        return self.errors

    def clear_errors(self) -> None:
        """Clear collected errors"""
        self.errors = []

    def has_critical_errors(self) -> bool:
        """Check if there are any critical errors"""
        return any(error['severity'] == 'critical' for error in self.errors)

    def validate_model(self, model_class: type, data: Dict[str, Any]) -> Optional[BaseModel]:
        """
        Validate data against Pydantic model

        Args:
            model_class: Pydantic model class
            data: Data to validate

        Returns:
            Model instance or None if validation failed
        """
        try:
            return model_class(**data)
        except ValidationError as e:
            for error in e.errors():
                field = '.'.join(str(loc) for loc in error['loc'])
                message = f"Validation error in {field}: {error['msg']}"
                severity = 'critical' if self.strict_mode else 'warning'
                self.collect_error('validation', message, severity)

            if self.strict_mode:
                return None
            else:
                # Try to create model with available valid fields
                return self._create_partial_model(model_class, data)

    def _create_partial_model(self, model_class: type, data: Dict[str, Any]) -> Optional[BaseModel]:
        """
        Create model with only valid fields when in lenient mode

        Args:
            model_class: Pydantic model class
            data: Original data

        Returns:
            Partial model instance or None
        """
        # Get model fields
        model_fields = model_class.__fields__

        # Try to create model with only valid data
        valid_data = {}
        for field_name, field_info in model_fields.items():
            if field_name in data:
                try:
                    # Test if this field validates
                    test_data = {field_name: data[field_name]}
                    model_class.parse_obj(test_data)
                    valid_data[field_name] = data[field_name]
                except ValidationError:
                    # Skip invalid field
                    continue

        # Try to create model with valid data
        try:
            return model_class(**valid_data)
        except ValidationError:
            self.collect_error('validation', f"Could not create partial model for {model_class.__name__}", 'critical')
            return None