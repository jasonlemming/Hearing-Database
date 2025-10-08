/**
 * Admin Dashboard JavaScript
 *
 * Handles interactive features for the admin dashboard:
 * - Manual update triggering
 * - Real-time progress monitoring via AJAX polling
 * - Log streaming and display
 * - Recent changes loading
 * - Production diff comparison
 */

// Global state
let currentTaskId = null;
let pollInterval = null;
let logLineCount = 0;

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Initialize dashboard on page load
 */
function initializeDashboard() {
    // Hookup form submission
    const form = document.getElementById('update-form');
    if (form) {
        form.addEventListener('submit', handleUpdateSubmit);
    }

    // Lookback slider
    const slider = document.getElementById('lookback-days');
    const display = document.getElementById('lookback-display');
    if (slider && display) {
        slider.addEventListener('input', (e) => {
            display.textContent = e.target.value;
        });
    }

    // Refresh changes button
    const refreshBtn = document.getElementById('refresh-changes');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            const date = document.getElementById('baseline-date').value;
            loadRecentChanges(date);
        });
    }

    // Cancel button
    const cancelBtn = document.getElementById('cancel-update-btn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', handleCancelUpdate);
    }

    // Initialize scheduling UI
    initializeScheduling();
}

/**
 * Handle update form submission
 */
async function handleUpdateSubmit(event) {
    event.preventDefault();

    // Gather form data
    const lookbackDays = parseInt(document.getElementById('lookback-days').value);

    // Build components array - hearings is always included
    const components = ['hearings'];

    if (document.getElementById('comp-witnesses').checked) {
        components.push('witnesses');
    }
    if (document.getElementById('comp-committees').checked) {
        components.push('committees');
    }

    const chamber = document.querySelector('input[name="chamber"]:checked').value;
    const dryRun = document.getElementById('dry-run').checked;

    // Disable form
    const submitBtn = document.getElementById('start-update-btn');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Starting...';

    try {
        // Start update
        const response = await fetch('/admin/api/start-update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                lookback_days: lookbackDays,
                components: components,
                chamber: chamber,
                dry_run: dryRun
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to start update');
        }

        // Store task ID and start polling
        currentTaskId = data.task_id;

        // Show progress container
        document.getElementById('progress-container').style.display = 'block';

        // Reset progress UI
        resetProgressUI();

        // Start polling
        startPolling(currentTaskId);

        // Show alert
        const alert = document.getElementById('current-task-alert');
        const message = document.getElementById('current-task-message');
        message.textContent = `Update task ${currentTaskId.substring(0, 8)}... started successfully`;
        alert.style.display = 'block';

    } catch (error) {
        alert('Error starting update: ' + error.message);
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-play me-2"></i>Start Update';
    }
}

/**
 * Reset progress UI to initial state
 */
function resetProgressUI() {
    // Progress bar
    updateProgress(0);

    // Stats
    document.getElementById('stat-checked').textContent = '0';
    document.getElementById('stat-updated').textContent = '0';
    document.getElementById('stat-added').textContent = '0';
    document.getElementById('stat-errors').textContent = '0';

    // Status
    document.getElementById('current-status').innerHTML = '<i class="fas fa-clock me-2"></i>Starting update...';

    // Clear logs and changes
    document.getElementById('log-output').textContent = '';
    document.getElementById('change-items').innerHTML = '';
    logLineCount = 0;
}

/**
 * Start AJAX polling for task status
 */
function startPolling(taskId) {
    // Clear any existing interval
    if (pollInterval) {
        clearInterval(pollInterval);
    }

    // Poll every 2 seconds
    pollInterval = setInterval(() => {
        pollTaskStatus(taskId);
    }, 2000);

    // Immediate first poll
    pollTaskStatus(taskId);
}

/**
 * Stop polling
 */
function stopPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

/**
 * Poll task status from server
 */
async function pollTaskStatus(taskId) {
    try {
        const response = await fetch(`/admin/api/task-status/${taskId}`);

        if (!response.ok) {
            throw new Error('Failed to get task status');
        }

        const data = await response.json();

        // Update UI
        updateProgressUI(data);

        // Check if complete
        if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
            stopPolling();
            handleTaskCompletion(data);
        }

    } catch (error) {
        console.error('Error polling task status:', error);
        // Don't stop polling on transient errors
    }
}

/**
 * Update progress UI with latest data
 */
function updateProgressUI(data) {
    // Parse recent logs for progress messages
    let latestProgress = null;
    if (data.recent_logs && data.recent_logs.length > 0) {
        // Look for the most recent progress message
        for (let i = data.recent_logs.length - 1; i >= 0; i--) {
            const line = data.recent_logs[i];
            try {
                const parsed = JSON.parse(line);
                if (parsed.type === 'progress' && parsed.data) {
                    latestProgress = parsed.data;
                    break;  // Found most recent progress
                }
            } catch (e) {
                // Not JSON or parsing failed, skip
            }
        }
    }

    // Use progress data from JSON messages if available
    const progress = latestProgress || data.progress || {};
    const percent = progress.percent || 0;
    updateProgress(percent);

    // Update stats
    document.getElementById('stat-checked').textContent = progress.hearings_checked || 0;
    document.getElementById('stat-updated').textContent = progress.hearings_updated || 0;
    document.getElementById('stat-added').textContent = progress.hearings_added || 0;
    document.getElementById('stat-errors').textContent = data.error_count || 0;

    // Update status message
    const statusEl = document.getElementById('current-status');
    const duration = data.duration_seconds ? formatDuration(data.duration_seconds) : '0s';

    // Add progress info to status if available
    if (latestProgress && latestProgress.total_hearings) {
        statusEl.innerHTML = `<i class="fas fa-sync fa-spin me-2"></i>Checking hearings (${latestProgress.hearings_checked}/${latestProgress.total_hearings})...`;
    } else {
        statusEl.innerHTML = `<i class="fas fa-clock me-2"></i>Running for ${duration}...`;
    }

    // Update recent logs
    if (data.recent_logs && data.recent_logs.length > 0) {
        appendLogs(data.recent_logs);
    }

    // Show recent changes if available
    if (progress.recent_changes) {
        updateRecentChangesList(progress.recent_changes);
    }
}

/**
 * Update progress bar
 */
function updateProgress(percent) {
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');

    progressBar.style.width = percent + '%';
    progressBar.setAttribute('aria-valuenow', percent);
    progressText.textContent = Math.round(percent) + '%';

    // Change color based on progress
    progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated';
    if (percent >= 100) {
        progressBar.classList.add('bg-success');
    } else if (percent >= 50) {
        progressBar.classList.add('bg-info');
    }
}

/**
 * Append new logs to log viewer
 */
function appendLogs(logs) {
    const logOutput = document.getElementById('log-output');

    logs.forEach(line => {
        logOutput.textContent += line + '\n';
        logLineCount++;
    });

    // Auto-scroll to bottom if details are open
    const details = document.getElementById('log-details');
    if (details.open) {
        logOutput.scrollTop = logOutput.scrollHeight;
    }
}

/**
 * Update recent changes list in progress panel
 */
function updateRecentChangesList(changes) {
    const listEl = document.getElementById('change-items');

    changes.forEach(change => {
        const li = document.createElement('li');
        li.className = 'list-group-item list-group-item-action';

        let icon, typeClass;
        if (change.type === 'added') {
            icon = 'plus';
            typeClass = 'change-added';
        } else if (change.type === 'updated') {
            icon = 'edit';
            typeClass = 'change-updated';
        } else {
            icon = 'exclamation-triangle';
            typeClass = 'change-error';
        }

        li.innerHTML = `
            <i class="fas fa-${icon} ${typeClass} me-2"></i>
            <span class="${typeClass}">${change.type.toUpperCase()}</span>:
            Hearing ${change.event_id} - ${change.title || '(No title)'}
        `;

        listEl.appendChild(li);
    });

    // Keep only last 10
    while (listEl.children.length > 10) {
        listEl.removeChild(listEl.firstChild);
    }
}

/**
 * Handle task completion
 */
function handleTaskCompletion(data) {
    const statusEl = document.getElementById('current-status');
    const submitBtn = document.getElementById('start-update-btn');

    // Re-enable form
    submitBtn.disabled = false;
    submitBtn.innerHTML = '<i class="fas fa-play me-2"></i>Start Update';

    // Hide alert
    document.getElementById('current-task-alert').style.display = 'none';

    if (data.status === 'completed') {
        statusEl.innerHTML = '<i class="fas fa-check-circle text-success me-2"></i>Update completed successfully!';
        updateProgress(100);

        // Show completion message
        const result = data.result || {};
        showCompletionSummary(result);

        // Show Copy Logs button
        const copyBtn = document.getElementById('copy-logs-btn');
        copyBtn.style.display = 'block';
        copyBtn.onclick = copyLogsToClipboard;

        // Change cancel button to "Close" button
        const cancelBtn = document.getElementById('cancel-update-btn');
        cancelBtn.innerHTML = '<i class="fas fa-times me-1"></i> Close';
        cancelBtn.classList.remove('btn-danger');
        cancelBtn.classList.add('btn-secondary');
        cancelBtn.onclick = () => {
            document.getElementById('progress-container').style.display = 'none';
            location.reload();  // Reload to refresh stats
        };

    } else if (data.status === 'failed') {
        statusEl.innerHTML = '<i class="fas fa-times-circle text-danger me-2"></i>Update failed: ' + (data.error_message || 'Unknown error');

        // Show Copy Logs button
        const copyBtn = document.getElementById('copy-logs-btn');
        copyBtn.style.display = 'block';
        copyBtn.onclick = copyLogsToClipboard;

        // Change cancel button to "Close" button
        const cancelBtn = document.getElementById('cancel-update-btn');
        cancelBtn.innerHTML = '<i class="fas fa-times me-1"></i> Close';
        cancelBtn.classList.remove('btn-danger');
        cancelBtn.classList.add('btn-secondary');
        cancelBtn.onclick = () => {
            document.getElementById('progress-container').style.display = 'none';
            location.reload();
        };

    } else if (data.status === 'cancelled') {
        statusEl.innerHTML = '<i class="fas fa-ban text-warning me-2"></i>Update was cancelled';

        // Show Copy Logs button
        const copyBtn = document.getElementById('copy-logs-btn');
        copyBtn.style.display = 'block';
        copyBtn.onclick = copyLogsToClipboard;

        // Change cancel button to "Close" button
        const cancelBtn = document.getElementById('cancel-update-btn');
        cancelBtn.innerHTML = '<i class="fas fa-times me-1"></i> Close';
        cancelBtn.classList.remove('btn-danger');
        cancelBtn.classList.add('btn-secondary');
        cancelBtn.onclick = () => {
            document.getElementById('progress-container').style.display = 'none';
            location.reload();
        };
    }
}

/**
 * Show completion summary
 */
function showCompletionSummary(result) {
    const message = `
        Update completed!
        - ${result.hearings_updated || 0} hearings updated
        - ${result.hearings_added || 0} hearings added
        - ${result.hearings_checked || 0} hearings checked
        ${result.error_count > 0 ? `\n- ${result.error_count} errors encountered` : ''}
    `;

    alert(message);
}

/**
 * Handle cancel update
 */
async function handleCancelUpdate() {
    if (!currentTaskId) {
        return;
    }

    if (!confirm('Are you sure you want to cancel the running update?')) {
        return;
    }

    try {
        const response = await fetch(`/admin/api/cancel-update/${currentTaskId}`, {
            method: 'POST'
        });

        if (response.ok) {
            stopPolling();
            document.getElementById('current-status').innerHTML =
                '<i class="fas fa-ban text-warning me-2"></i>Cancelling update...';
        } else {
            alert('Failed to cancel update');
        }

    } catch (error) {
        alert('Error cancelling update: ' + error.message);
    }
}

/**
 * Load recent changes from server
 */
async function loadRecentChanges(sinceDate) {
    const loadingEl = document.getElementById('changes-loading');
    const contentEl = document.getElementById('changes-content');
    const tbody = document.getElementById('changes-tbody');

    // Show loading
    loadingEl.style.display = 'block';
    contentEl.style.display = 'none';

    try {
        const response = await fetch(`/admin/api/recent-changes?since=${sinceDate}&limit=50`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to load changes');
        }

        // Populate table
        tbody.innerHTML = '';

        if (data.changes.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No changes found since ' + sinceDate + '</td></tr>';
        } else {
            data.changes.forEach(change => {
                const row = document.createElement('tr');

                const changeClass = change.change_type === 'added' ? 'text-success' : 'text-info';
                const changeIcon = change.change_type === 'added' ? 'plus' : 'edit';

                row.innerHTML = `
                    <td><code>${change.event_id}</code></td>
                    <td>${truncate(change.title, 60)}</td>
                    <td><span class="badge bg-secondary">${change.chamber}</span></td>
                    <td>${formatDate(change.hearing_date)}</td>
                    <td>
                        <span class="badge bg-light ${changeClass}">
                            <i class="fas fa-${changeIcon} me-1"></i>${change.change_type.toUpperCase()}
                        </span>
                    </td>
                    <td>${formatDateTime(change.updated_at)}</td>
                `;

                tbody.appendChild(row);
            });
        }

        // Show content
        loadingEl.style.display = 'none';
        contentEl.style.display = 'block';

    } catch (error) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Error loading changes: ' + error.message + '</td></tr>';
        loadingEl.style.display = 'none';
        contentEl.style.display = 'block';
    }
}

/**
 * Load production diff stats
 */
async function loadProductionDiff() {
    try {
        const response = await fetch('/admin/api/production-diff');
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to load production diff');
        }

        // Update stats cards if needed
        console.log('Production diff:', data);

    } catch (error) {
        console.error('Error loading production diff:', error);
    }
}

/**
 * Format duration in seconds to human-readable string
 */
function formatDuration(seconds) {
    if (seconds < 60) {
        return Math.round(seconds) + 's';
    } else if (seconds < 3600) {
        return Math.round(seconds / 60) + 'm ' + Math.round(seconds % 60) + 's';
    } else {
        return Math.round(seconds / 3600) + 'h ' + Math.round((seconds % 3600) / 60) + 'm';
    }
}

/**
 * Format date string
 */
function formatDate(dateStr) {
    if (!dateStr) return '-';
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString();
    } catch (e) {
        return dateStr;
    }
}

/**
 * Format datetime string
 */
function formatDateTime(dateStr) {
    if (!dateStr) return '-';
    try {
        const date = new Date(dateStr);
        return date.toLocaleString();
    } catch (e) {
        return dateStr;
    }
}

/**
 * Truncate string to max length
 */
function truncate(str, maxLen) {
    if (!str) return '-';
    if (str.length <= maxLen) return str;
    return str.substring(0, maxLen) + '...';
}

/**
 * Copy logs to clipboard
 */
async function copyLogsToClipboard() {
    const logOutput = document.getElementById('log-output');
    if (!logOutput) {
        alert('No logs available to copy');
        return;
    }

    const logText = logOutput.textContent;

    if (!logText || logText.trim() === '') {
        alert('No logs available to copy');
        return;
    }

    try {
        await navigator.clipboard.writeText(logText);

        // Show success feedback
        const btn = document.getElementById('copy-logs-btn');
        const originalHtml = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-check me-1"></i> Copied!';
        btn.classList.remove('btn-light');
        btn.classList.add('btn-success');

        setTimeout(() => {
            btn.innerHTML = originalHtml;
            btn.classList.remove('btn-success');
            btn.classList.add('btn-light');
        }, 2000);

    } catch (err) {
        console.error('Failed to copy logs:', err);
        alert('Failed to copy logs to clipboard. Error: ' + err.message);
    }
}

// ============================================================================
// SCHEDULING FUNCTIONALITY
// ============================================================================

let currentEditingScheduleId = null;

/**
 * Initialize scheduling UI
 */
function initializeScheduling() {
    // Load schedules and execution history
    loadSchedules();
    loadExecutions();

    // Create schedule button
    const createBtn = document.getElementById('btn-create-schedule');
    if (createBtn) {
        createBtn.addEventListener('click', () => showScheduleModal());
    }

    // Schedule form submission
    const scheduleForm = document.getElementById('schedule-form');
    if (scheduleForm) {
        scheduleForm.addEventListener('submit', handleScheduleSubmit);
    }

    // Schedule lookback slider
    const schedLookback = document.getElementById('schedule-lookback');
    const schedLookbackDisplay = document.getElementById('lookback-value');
    if (schedLookback && schedLookbackDisplay) {
        schedLookback.addEventListener('input', (e) => {
            schedLookbackDisplay.textContent = e.target.value;
        });
    }

    // Save schedule button
    const saveBtn = document.getElementById('btn-save-schedule');
    if (saveBtn) {
        saveBtn.addEventListener('click', (e) => {
            e.preventDefault();
            handleScheduleSubmit(new Event('submit'));
        });
    }

    // Export Vercel button
    const exportVercelBtn = document.getElementById('btn-export-vercel');
    if (exportVercelBtn) {
        exportVercelBtn.addEventListener('click', handleExportVercel);
    }

    // Copy Vercel config button
    const copyVercelBtn = document.getElementById('btn-copy-vercel');
    if (copyVercelBtn) {
        copyVercelBtn.addEventListener('click', copyVercelConfig);
    }
}

/**
 * Load and display schedules
 */
async function loadSchedules() {
    const tbody = document.getElementById('schedules-tbody');
    const loadingEl = document.getElementById('schedules-loading');
    const contentEl = document.getElementById('schedules-content');
    const emptyEl = document.getElementById('schedules-empty');

    if (loadingEl) loadingEl.style.display = 'block';
    if (contentEl) contentEl.style.display = 'none';
    if (emptyEl) emptyEl.style.display = 'none';

    try {
        const response = await fetch('/admin/api/schedules');
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to load schedules');
        }

        // Populate table
        if (tbody) {
            tbody.innerHTML = '';

            if (data.schedules.length === 0) {
                if (loadingEl) loadingEl.style.display = 'none';
                if (emptyEl) emptyEl.style.display = 'block';
            } else {
                data.schedules.forEach(schedule => {
                    tbody.appendChild(createScheduleRow(schedule));
                });
                if (loadingEl) loadingEl.style.display = 'none';
                if (contentEl) contentEl.style.display = 'block';

                // Check for undeployed schedules and show warning
                checkDeploymentStatus(data.schedules);
            }
        }

    } catch (error) {
        console.error('Error loading schedules:', error);
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Error loading schedules: ${error.message}</td></tr>`;
        }
        if (loadingEl) loadingEl.style.display = 'none';
        if (contentEl) contentEl.style.display = 'block';
    }
}

/**
 * Check deployment status and show warning if needed
 */
function checkDeploymentStatus(schedules) {
    const warningEl = document.getElementById('deployment-warning');
    const messageEl = document.getElementById('deployment-warning-message');

    if (!warningEl || !messageEl) return;

    // Find active schedules that aren't deployed
    const undeployedActive = schedules.filter(s => s.is_active && !s.is_deployed);

    if (undeployedActive.length > 0) {
        const scheduleNames = undeployedActive.map(s => `<strong>${escapeHtml(s.name)}</strong>`).join(', ');
        messageEl.innerHTML = `You have ${undeployedActive.length} active schedule(s) that are not deployed to Vercel: ${scheduleNames}.<br>
                               These schedules will not run automatically until they are deployed.`;
        warningEl.style.display = 'block';
    } else {
        warningEl.style.display = 'none';
    }
}

/**
 * Create a table row for a schedule
 */
function createScheduleRow(schedule) {
    const row = document.createElement('tr');

    // Status badge
    const statusClass = schedule.is_active ? 'bg-success' : 'bg-secondary';
    const statusText = schedule.is_active ? 'Active' : 'Inactive';

    // Deployment badge
    const deployClass = schedule.is_deployed ? 'bg-primary' : 'bg-warning';
    const deployText = schedule.is_deployed ? 'Deployed' : 'Not Deployed';

    // Components array
    let components = [];
    try {
        components = JSON.parse(schedule.components || '[]');
    } catch (e) {
        components = [];
    }

    row.innerHTML = `
        <td><strong>${schedule.name}</strong></td>
        <td><code>${schedule.schedule_cron}</code></td>
        <td>${schedule.lookback_days} days</td>
        <td>
            ${components.map(c => `<span class="badge bg-light text-dark me-1">${c}</span>`).join('')}
        </td>
        <td><span class="badge ${statusClass}">${statusText}</span></td>
        <td><span class="badge ${deployClass}">${deployText}</span></td>
        <td>
            <button class="btn btn-sm btn-info me-1" onclick="testSchedule(${schedule.task_id})"
                    title="Test this schedule now">
                <i class="fas fa-play"></i> Test
            </button>
            <button class="btn btn-sm btn-primary me-1" onclick="editSchedule(${schedule.task_id})">
                <i class="fas fa-edit"></i> Edit
            </button>
            <button class="btn btn-sm btn-${schedule.is_active ? 'warning' : 'success'} me-1"
                    onclick="toggleSchedule(${schedule.task_id})">
                <i class="fas fa-power-off"></i> ${schedule.is_active ? 'Disable' : 'Enable'}
            </button>
            <button class="btn btn-sm btn-danger" onclick="deleteSchedule(${schedule.task_id})">
                <i class="fas fa-trash"></i> Delete
            </button>
        </td>
    `;

    return row;
}

/**
 * Load execution history
 */
async function loadExecutions() {
    const loadingEl = document.getElementById('executions-loading');
    const contentEl = document.getElementById('executions-content');
    const emptyEl = document.getElementById('executions-empty');
    const tbody = document.getElementById('executions-tbody');

    // Show loading
    loadingEl.style.display = 'block';
    contentEl.style.display = 'none';
    emptyEl.style.display = 'none';

    try {
        const response = await fetch('/admin/api/executions?limit=20');
        if (!response.ok) throw new Error('Failed to load execution history');

        const data = await response.json();
        const executions = data.executions || [];

        if (executions.length === 0) {
            loadingEl.style.display = 'none';
            emptyEl.style.display = 'block';
            return;
        }

        // Clear and populate table
        tbody.innerHTML = '';
        executions.forEach(exec => {
            const row = createExecutionRow(exec);
            tbody.appendChild(row);
        });

        loadingEl.style.display = 'none';
        contentEl.style.display = 'block';

    } catch (error) {
        console.error('Error loading executions:', error);
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger">Failed to load execution history</td></tr>';
        loadingEl.style.display = 'none';
        contentEl.style.display = 'block';
    }
}

/**
 * Create execution history table row
 */
function createExecutionRow(exec) {
    const row = document.createElement('tr');

    // Status badge
    const statusBadge = exec.success
        ? '<span class="badge bg-success"><i class="fas fa-check"></i> Success</span>'
        : '<span class="badge bg-danger"><i class="fas fa-times"></i> Failed</span>';

    // Source badge
    const sourceBadges = {
        'manual': '<span class="badge bg-primary">Manual</span>',
        'vercel_cron': '<span class="badge bg-info">Cron</span>',
        'test': '<span class="badge bg-warning">Test</span>'
    };
    const sourceBadge = sourceBadges[exec.trigger_source] || '<span class="badge bg-secondary">Unknown</span>';

    // Format duration
    const duration = exec.duration_seconds ? `${Math.round(exec.duration_seconds)}s` : '-';

    // Format time
    const execTime = new Date(exec.execution_time).toLocaleString();

    // Hearings summary
    const hearingsSummary = exec.hearings_checked > 0
        ? `${exec.hearings_updated}/${exec.hearings_checked}`
        : '-';

    row.innerHTML = `
        <td><strong>${escapeHtml(exec.schedule_name)}</strong></td>
        <td>${execTime}</td>
        <td>${statusBadge}</td>
        <td>${duration}</td>
        <td>${hearingsSummary}</td>
        <td>${sourceBadge}</td>
        <td>
            ${exec.success ? '' : `<small class="text-danger">${escapeHtml(exec.error_message || '')}</small>`}
        </td>
    `;

    return row;
}

/**
 * Show schedule modal for create/edit
 */
function showScheduleModal(schedule = null) {
    currentEditingScheduleId = schedule ? schedule.task_id : null;

    const modal = document.getElementById('scheduleModal');
    const modalTitle = document.getElementById('scheduleModalTitle');
    const form = document.getElementById('schedule-form');

    if (schedule) {
        // Edit mode
        modalTitle.textContent = 'Edit Schedule';

        // Populate form
        document.getElementById('schedule-name').value = schedule.name || '';
        document.getElementById('schedule-description').value = schedule.description || '';
        document.getElementById('schedule-cron').value = schedule.schedule_cron || '';
        document.getElementById('schedule-lookback').value = schedule.lookback_days || 7;
        document.getElementById('lookback-value').textContent = schedule.lookback_days || 7;
        document.getElementById('schedule-chamber').value = schedule.chamber || 'both';
        document.getElementById('schedule-mode').value = schedule.mode || 'incremental';
        document.getElementById('schedule-active').checked = schedule.is_active || false;

        // Parse components
        let components = [];
        try {
            components = Array.isArray(schedule.components) ? schedule.components : JSON.parse(schedule.components || '[]');
        } catch (e) {
            components = [];
        }

        document.getElementById('comp-hearings-modal').checked = true; // Always checked
        document.getElementById('comp-committees-modal').checked = components.includes('committees');
        document.getElementById('comp-witnesses-modal').checked = components.includes('witnesses');

    } else {
        // Create mode
        modalTitle.textContent = 'Create New Schedule';
        form.reset();
        document.getElementById('lookback-value').textContent = '7';
        document.getElementById('comp-hearings-modal').checked = true; // Default to hearings
        document.getElementById('comp-committees-modal').checked = true;
        document.getElementById('comp-witnesses-modal').checked = true;
    }

    // Show modal
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
}

/**
 * Handle schedule form submission
 */
async function handleScheduleSubmit(event) {
    event.preventDefault();

    // Gather form data
    const name = document.getElementById('schedule-name').value;
    const description = document.getElementById('schedule-description').value;
    const schedule_cron = document.getElementById('schedule-cron').value;
    const lookback_days = parseInt(document.getElementById('schedule-lookback').value);
    const chamber = document.getElementById('schedule-chamber').value;
    const mode = document.getElementById('schedule-mode').value;
    const is_active = document.getElementById('schedule-active').checked;

    // Build components array
    const components = [];
    if (document.getElementById('comp-hearings-modal').checked) {
        components.push('hearings');
    }
    if (document.getElementById('comp-committees-modal').checked) {
        components.push('committees');
    }
    if (document.getElementById('comp-witnesses-modal').checked) {
        components.push('witnesses');
    }

    // Validation
    if (!name || !schedule_cron || components.length === 0) {
        alert('Please fill in all required fields (name, schedule, and at least one component)');
        return;
    }

    const payload = {
        name,
        description,
        schedule_cron,
        lookback_days,
        components: JSON.stringify(components),
        chamber,
        mode,
        is_active
    };

    try {
        let response;
        if (currentEditingScheduleId) {
            // Update existing
            response = await fetch(`/admin/api/schedules/${currentEditingScheduleId}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
        } else {
            // Create new
            response = await fetch('/admin/api/schedules', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to save schedule');
        }

        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('scheduleModal'));
        modal.hide();

        // Reload schedules
        loadSchedules();

        // Show success message
        alert(data.message || 'Schedule saved successfully');

    } catch (error) {
        alert('Error saving schedule: ' + error.message);
    }
}

/**
 * Edit a schedule
 */
async function editSchedule(taskId) {
    try {
        const response = await fetch(`/admin/api/schedules/${taskId}`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to load schedule');
        }

        showScheduleModal(data.schedule);

    } catch (error) {
        alert('Error loading schedule: ' + error.message);
    }
}

/**
 * Test a schedule (trigger it manually)
 */
async function testSchedule(taskId) {
    // Confirm with user
    if (!confirm('This will run the schedule update immediately. Continue?')) {
        return;
    }

    const button = event.target.closest('button');
    const originalHtml = button.innerHTML;

    try {
        // Show loading state
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';

        const response = await fetch(`/admin/api/schedules/${taskId}/test`, {
            method: 'POST'
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Test failed');
        }

        // Show success message with metrics
        let message = `✅ Test completed successfully!\n\n`;
        if (data.metrics) {
            message += `Hearings checked: ${data.metrics.hearings_checked || 0}\n`;
            message += `Hearings updated: ${data.metrics.hearings_updated || 0}\n`;
            message += `Hearings added: ${data.metrics.hearings_added || 0}\n`;
            message += `Duration: ${data.metrics.duration ? Math.round(data.metrics.duration) + 's' : 'N/A'}`;
        }
        alert(message);

        // Reload execution history to show the new test run
        loadExecutions();

    } catch (error) {
        alert('❌ Test failed: ' + error.message);
    } finally {
        // Restore button
        button.disabled = false;
        button.innerHTML = originalHtml;
    }
}

/**
 * Toggle schedule active status
 */
async function toggleSchedule(taskId) {
    try {
        const response = await fetch(`/admin/api/schedules/${taskId}/toggle`, {
            method: 'POST'
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to toggle schedule');
        }

        // Reload schedules
        loadSchedules();

    } catch (error) {
        alert('Error toggling schedule: ' + error.message);
    }
}

/**
 * Delete a schedule
 */
async function deleteSchedule(taskId) {
    if (!confirm('Are you sure you want to delete this schedule?')) {
        return;
    }

    try {
        const response = await fetch(`/admin/api/schedules/${taskId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to delete schedule');
        }

        // Reload schedules
        loadSchedules();

        alert('Schedule deleted successfully');

    } catch (error) {
        alert('Error deleting schedule: ' + error.message);
    }
}

/**
 * Handle Vercel config export
 */
async function handleExportVercel() {
    try {
        const response = await fetch('/admin/api/schedules/export-vercel');
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to export Vercel config');
        }

        // Display in modal
        const output = document.getElementById('vercel-config-output');
        output.textContent = JSON.stringify(data.config, null, 2);

        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('vercelExportModal'));
        modal.show();

    } catch (error) {
        alert('Error exporting Vercel config: ' + error.message);
    }
}

/**
 * Copy Vercel config to clipboard
 */
async function copyVercelConfig() {
    const output = document.getElementById('vercel-config-output');
    const text = output.textContent;

    try {
        await navigator.clipboard.writeText(text);

        // Show success feedback
        const btn = document.getElementById('btn-copy-vercel');
        const originalHtml = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-check me-1"></i> Copied!';
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-success');

        setTimeout(() => {
            btn.innerHTML = originalHtml;
            btn.classList.remove('btn-success');
            btn.classList.add('btn-primary');
        }, 2000);

    } catch (err) {
        console.error('Failed to copy config:', err);
        alert('Failed to copy to clipboard');
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeDashboard);
} else {
    initializeDashboard();
}
