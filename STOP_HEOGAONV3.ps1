$ports = @(4100, 3103)

foreach ($port in $ports) {
  Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object {
      Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
      Write-Host "Stopped process on port $port"
    }
}
