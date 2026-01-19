 = [Environment]::GetEnvironmentVariable('PATH','User')
if(-not ( -like '*C:\Users\ksowu\.fly\bin*')) {
    [Environment]::SetEnvironmentVariable('PATH',  + ';C:\\Users\\ksowu\\.fly\\bin', 'User')
}
