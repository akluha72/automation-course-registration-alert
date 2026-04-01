# Run this script ONCE in PowerShell as Administrator to register the Task Scheduler job.
# It will re-run init.py every 10 minutes automatically, no terminal needed.

$pythonPath = "C:\laragon\bin\python\python-3.10\python.exe"
$scriptPath = "C:\laragon\www\automation-uitm-course-registration\init.py"
$workDir    = "C:\laragon\www\automation-uitm-course-registration"
$taskName   = "UiTM-ECR-Monitor"

$action  = New-ScheduledTaskAction `
    -Execute "$workDir\run.bat" `
    -WorkingDirectory $workDir

$trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 10) -Once -At (Get-Date)

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 8) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable

# Run as the current logged-in user so Playwright/Chromium can be found
$principal = New-ScheduledTaskPrincipal `
    -UserId  "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName  $taskName `
    -Action    $action `
    -Trigger   $trigger `
    -Settings  $settings `
    -Principal $principal `
    -Force

Write-Host ""
Write-Host "Task '$taskName' registered. It will run every 1 minute."
Write-Host "To stop it:  Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
Write-Host "To run now:  Start-ScheduledTask -TaskName '$taskName'"
