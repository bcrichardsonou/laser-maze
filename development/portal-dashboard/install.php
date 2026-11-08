<?php
// Run through Bluehost CLI from private staging, never place in website root.
if (PHP_SAPI!=='cli') exit('CLI only');
$root='/srv/zoco/public_html/manage';
$base=__DIR__.'/public';$path=$root.'/views/exhibit.php';
$text=file_get_contents($path);$marker='function render_exhibit(array $e,bool $detail,bool $shared=false,?array $viewer=null): void {';
$hook="\n    // ZoCo Laser Maze detailed dashboard\n    if (\$detail && !\$shared && preg_match('/^laser\\s*maze$/i',trim(\$e['name']))) {\n        require_once __DIR__.'/laser-maze.php';\n        render_laser_maze(\$e,\$viewer);\n        return;\n    }\n";
if ($text===false || substr_count($text,$marker)!==1) exit("Unexpected exhibit view; no changes made.\n");
if (str_contains($text,'ZoCo Laser Maze detailed dashboard')) exit("Dashboard already installed; inspect before replacing it.\n");
$updated=str_replace($marker,$marker.$hook,$text);
$files=[$base.'/views/laser-maze.php'=>$root.'/views/laser-maze.php',$base.'/assets/laser-maze.css'=>$root.'/assets/laser-maze.css'];
foreach($files as $source=>$target)if(!is_file($source)||file_exists($target))exit("Missing source or existing target; no changes made.\n");
if (!is_dir($root.'/assets') || !is_dir($root.'/views'))exit("Missing portal folders; no changes made.\n");
$backup=__DIR__.'/backups-'.date('Ymd-His');if(!mkdir($backup,0700))exit("Cannot create backup.\n");
if(!copy($path,$backup.'/exhibit.php'))exit("Backup failed.\n");chmod($backup.'/exhibit.php',0600);
$temp=tempnam(__DIR__,'.view-');if(file_put_contents($temp,$updated)!==strlen($updated))exit("Cannot stage view.\n");
foreach([$temp,$base.'/views/laser-maze.php'] as $php){exec(escapeshellarg(PHP_BINARY).' -l '.escapeshellarg($php),$output,$status);if($status!==0){unlink($temp);exit("Syntax check failed; live view unchanged.\n");}}
foreach($files as $source=>$target){if(!copy($source,$target))exit("Asset copy failed; original view still active.\n");chmod($target,0644);}
chmod($temp,fileperms($path)&0777);if(!rename($temp,$path))exit("View install failed; original still active.\n");
echo "Laser Maze dashboard installed. Other exhibit views preserved. Backup: $backup/exhibit.php\n";
