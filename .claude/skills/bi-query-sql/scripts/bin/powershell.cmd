@echo off
:: Windows shim: 将 powershell -EncodedCommand <b64> 转发给 catdesk browser-action
node "%~dp0open-shim.js" %*
