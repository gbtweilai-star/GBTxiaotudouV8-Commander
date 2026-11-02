param($path = '.')

Start-Process powershell -Wait -NoNewWindow -ArgumentList "-File `"$($MyInvocation.MyCommand.Fullname)`" `"$($path)\dsh-smoke.md`""