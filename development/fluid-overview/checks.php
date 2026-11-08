<?php
if(PHP_SAPI!=='cli')exit(1);
function one($sql,$args=[]){global $testLive;return ['value'=>json_encode(['received_at'=>time(),'data'=>$testLive])];}
function esc($s){return htmlspecialchars((string)$s,ENT_QUOTES,'UTF-8');}
require __DIR__.'/public/fluid-lib.php';
$n=0;function check($ok,$why){global $n;if(!$ok)throw new RuntimeException($why);$n++;}
$c=['id'=>5,'active'=>1,'exhibit_id'=>4,'location_id'=>2];
$testLive=['sampled_at'=>time(),'connected'=>true,'tank_level'=>['raw'=>45,'state'=>'reading','float_height_percent'=>100.0,'calibration'=>['empty_raw'=>268,'full_raw'=>45],'private'=>'DO_NOT_EXPOSE'],'private_key'=>'DO_NOT_EXPOSE'];
$p=fluid_summary($c,$testLive);check($p['percent']===100.0,'Full reading');check(array_keys($p)===['state','percent','updated_at'],'Minimal public projection');check(!str_contains(json_encode($p),'DO_NOT_EXPOSE'),'Private telemetry excluded');
foreach([0,25.5,100] as $v){$l=$testLive;$l['tank_level']['float_height_percent']=$v;check(fluid_summary($c,$l)['percent']==$v,'Bounded value preserved');}
foreach([-1,101,'100',null,NAN] as $v){$l=$testLive;$l['tank_level']['float_height_percent']=$v;check(fluid_summary($c,$l)['percent']===null,'Bad percent unconfirmed');}
$l=$testLive;$l['sampled_at']=time()-30;check(fluid_summary($c,$l)['state']==='unconfirmed','Stale data hidden');
$l=$testLive;$l['connected']=false;check(fluid_summary($c,$l)['state']==='unconfirmed','Disconnected data hidden');
$l=$testLive;$l['tank_level']['raw']=null;check(fluid_summary($c,$l)['state']==='unconfirmed','Stale A1 reading hidden');
$l=$testLive;$l['tank_level']['state']='uncalibrated';check(fluid_summary($c,$l)['state']==='uncalibrated','Calibration pending distinguished');
$l=$testLive;$l['tank_level']['state']='open_or_connected_to_5v';check(fluid_summary($c,$l)['state']==='check_sensor','Fault distinguished');
check(fluid_share_scope(['exhibit_id'=>4],$c),'Matching exhibit share');check(!fluid_share_scope(['exhibit_id'=>9,'location_id'=>2],$c),'Exhibit share cannot broaden to location');check(fluid_share_scope(['location_id'=>2],$c),'Matching location share');check(!fluid_share_scope(['location_id'=>3],$c),'Other location denied');check(!fluid_share_scope([],$c),'Empty scope denied');
ob_start();render_fluid_overview($c,false);$public=ob_get_clean();check(str_contains($public,'100%'),'Prominent full percentage');check(str_contains($public,'role="meter"'),'Accessible tank graphic');check(!str_contains($public,'Calibrate sender')&&!str_contains($public,'<form')&&!str_contains($public,'DO_NOT_EXPOSE'),'Public view read-only and sanitized');
ob_start();render_fluid_overview($c,true);$admin=ob_get_clean();check(str_contains($admin,'#maintenance-tank-5'),'Admin calibration shortcut');
file_put_contents(__DIR__.'/public-card.html',$public);file_put_contents(__DIR__.'/admin-card.html',$admin);
echo "$n fluid overview checks passed.\n";
