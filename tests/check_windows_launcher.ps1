param([string]$Path)
$tokens=$null;$errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile($Path,[ref]$tokens,[ref]$errors)
if($errors.Count){$errors | Format-List;exit 1}
'Windows launcher parsed successfully.'
