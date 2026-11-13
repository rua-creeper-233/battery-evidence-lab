"""Check the Windows launchers using the PowerShell shipped with Windows."""
import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"


@unittest.skipUnless(os.name == "nt" and POWERSHELL.is_file(), "Windows PowerShell required")
class StartupScriptTests(unittest.TestCase):
    def run_powershell(self, code):
        result = subprocess.run(
            [str(POWERSHELL), "-NoProfile", "-NonInteractive", "-Command", code],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def test_launchers_parse_with_windows_powershell_51(self):
        self.run_powershell("""
$scripts=Get-ChildItem -LiteralPath scripts -Filter '*.ps1'
if ($scripts.Count -lt 4) { throw 'Expected launchers and shared Python resolver' }
$scripts | ForEach-Object {
    $tokens=$null; $errors=$null
    [System.Management.Automation.Language.Parser]::ParseFile($_.FullName,[ref]$tokens,[ref]$errors) > $null
    if ($errors.Count) { throw ($_.Name + ': ' + ($errors.Message -join '; ')) }
}
""")

    def test_share_key_generation_works_without_starting_service(self):
        self.run_powershell("""
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PWD 'scripts/start-share.ps1'),[ref]$tokens,[ref]$errors)
$function=$ast.Find({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'New-ShareAccessKey'},$true)
if (-not $function) { throw 'Share key function missing' }
Invoke-Expression $function.Extent.Text
$first=New-ShareAccessKey
$second=New-ShareAccessKey
if ($first -cnotmatch '^[0-9a-f]{48}$' -or $second -cnotmatch '^[0-9a-f]{48}$' -or $first -eq $second) { throw 'Invalid share key' }
""")


if __name__ == "__main__":
    unittest.main()
