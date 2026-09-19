param(
  [Parameter(Mandatory=$true)][string]$Root,
  [Parameter(Mandatory=$true)][string]$EmployeeCode,
  [Parameter(Mandatory=$true)][string]$SamAccountName,
  [Parameter(Mandatory=$true)][string]$CentralServiceAccount
)

$UserRoot = Join-Path $Root $EmployeeCode
$State = Join-Path $UserRoot "state"
$Snapshot = Join-Path $UserRoot "snapshot"
New-Item -ItemType Directory -Force -Path $State,$Snapshot | Out-Null

# User root: traversal/read, no inherited broad ACL.
icacls $UserRoot /inheritance:r | Out-Null
icacls $UserRoot /grant:r "${SamAccountName}:(RX)" "${CentralServiceAccount}:(OI)(CI)F" "Administrators:(OI)(CI)F" | Out-Null

# Personal state: user can persist preferences.
icacls $State /inheritance:r | Out-Null
icacls $State /grant:r "${SamAccountName}:(OI)(CI)M" "${CentralServiceAccount}:(OI)(CI)F" "Administrators:(OI)(CI)F" | Out-Null

# Fresh snapshot: user is read-only; central publisher writes it.
icacls $Snapshot /inheritance:r | Out-Null
icacls $Snapshot /grant:r "${SamAccountName}:(OI)(CI)R" "${CentralServiceAccount}:(OI)(CI)F" "Administrators:(OI)(CI)F" | Out-Null

Write-Host "GSI ACL applied for $EmployeeCode / $SamAccountName"
