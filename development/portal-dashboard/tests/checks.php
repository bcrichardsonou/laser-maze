<?php
require '/app/public/lib.php';require '/app/public/views/laser-maze.php';
$_SESSION=['csrf'=>'preview'];
$passed=0;function check($ok,$message){global $passed;if(!$ok)throw new RuntimeException($message);$passed++;}
$now=new DateTimeImmutable('2026-10-13T16:00:00-05:00');
function row($id,$kind,$mode,$fast,$outcome=null,$cid=1,$time='2026-10-13 20:00:00') {
    $p=['session_id'=>sprintf('00000000-0000-0000-0000-%012d',$id),'bench_prototype'=>true,'fast_demo'=>$fast,'mode'=>$mode];
    if($outcome!==null)$p+=['outcome'=>$outcome,'elapsed_seconds'=>10,'break_count'=>1];
    return ['component_id'=>$cid,'kind'=>$kind,'occurred_at'=>$time,'payload'=>json_encode($p),'name'=>'Test Pi'];
}
$rows=[row(1,'bench_game_started','usb',true),row(1,'bench_game_result','usb',true,'win'),row(2,'bench_game_started','keys',true),row(2,'bench_game_result','keys',true,'beam_limit'),row(3,'bench_game_result','usb',false,'win'),row(4,'bench_game_result','usb',true,'stopped'),row(5,'bench_game_result','usb',true,'communication_fault')];
$s=maze_stats($rows,'America/Chicago',7,'all',$now);
check($s['starts']===2&&$s['results']===5,'starts/results count independently');
check($s['wins']===2&&$s['challenge_results']===3,'win denominator excludes stops and communication faults');
check(count($s['win_times']['fast'])===1&&count($s['win_times']['normal'])===1,'duration profiles separated');
check(count($s['days'])===7&&$s['today_starts']===2,'seven local days and today counts');
$s2=maze_stats(array_merge($rows,[$rows[1]]),'America/Chicago',7,'all',$now);check($s2['results']===5,'duplicate session/result not counted twice');
$fast=maze_stats($rows,'America/Chicago',7,'fast',$now);check($fast['results']===4&&$fast['wins']===1,'timing filter');
$cross=row(6,'bench_game_started','usb',true,null,1,'2026-10-13 03:00:00');$tz=maze_stats([$cross],'America/Chicago',7,'all',$now);check($tz['today_starts']===0&&$tz['days']['2026-10-12']['starts']===1,'UTC late hours mapped to previous local day');
$other=$rows[1];$p=json_decode($other['payload'],true);$p['bench_prototype']=false;$other['payload']=json_encode($p);check(maze_stats([$other],'America/Chicago',7,'all',$now)['results']===0,'nonbench record excluded');
$bad=$rows[1];$p=json_decode($bad['payload'],true);$p['session_id']='invalid';$bad['payload']=json_encode($p);check(maze_stats([$bad],'America/Chicago',7,'all',$now)['skipped']===1,'malformed identity excluded');
$_GET=['maze_days'=>999,'maze_timing'=>'<script>'];check(maze_settings()===[7,'all'],'invalid filters bounded');$_GET=[];
$p=db();$p->exec('CREATE TABLE zp_components(id INTEGER PRIMARY KEY,exhibit_id INTEGER,name TEXT,device_id TEXT,active INTEGER,state TEXT,state_at TEXT,last_contact TEXT,state_payload TEXT);CREATE TABLE zp_events(component_id INTEGER,kind TEXT,occurred_at TEXT,payload TEXT);CREATE TABLE zp_settings(name TEXT,value TEXT);');
$metrics=['bench_prototype'=>true,'fast_demo'=>true,'game_phase'=>'finished','game_mode'=>'keys','arduino_connected'=>true,'keypad_available'=>true,'remaining_seconds'=>0,'break_count'=>1,'key_progress'=>0,'objective_completed'=>false,'last_result'=>'win','beam1_input_active'=>false,'beam2_input_active'=>false,'beam1_commanded_on'=>false,'beam2_commanded_on'=>false,'firmware_version'=>'bench-0.6.0','python_version'=>'bench-0.6.0','rgb_requested'=>'GREEN'];
$payload=json_encode(['state'=>'ready','metrics'=>$metrics]);$timestamp=gmdate('Y-m-d H:i:s');
q('INSERT INTO zp_components VALUES(?,?,?,?,?,?,?,?,?)',[1,4,'Bench Pi <script>','demo-device',1,'ready',$timestamp,$timestamp,$payload]);
q('INSERT INTO zp_components VALUES(?,?,?,?,?,?,?,?,?)',[2,2,'Other exhibit', 'other',1,'ready',$timestamp,$timestamp,$payload]);
foreach($rows as $r)q('INSERT INTO zp_events VALUES(?,?,?,?)',[$r['component_id'],$r['kind'],$timestamp,$r['payload']]);
q('INSERT INTO zp_events VALUES(?,?,?,?)',[2,'bench_game_result',$timestamp,json_encode(['session_id'=>'00000000-0000-0000-0000-000000000099','bench_prototype'=>true,'fast_demo'=>true,'mode'=>'usb','outcome'=>'win'])]);
$e=['id'=>4,'name'=>'Laser Maze','timezone'=>'America/Chicago','museum_name'=>'Sample museum','location_name'=>'Sample room','point_user_id'=>null];
$read=maze_read_stats(4,$e['timezone'],7,'all');check($read['results']===5,'other exhibit excluded by database query');
check(maze_live(components(4)[0]),'fresh state accepted');$stale=components(4)[0];$stale['state_at']='2020-01-01 00:00:00';check(!maze_live($stale),'stale state rejected even with recent heartbeat');
ob_start();header_page('Laser Maze preview',['name'=>'Sample admin','role'=>'admin']);echo '<p class="alert">Layout preview · synthetic test records</p>';render_laser_maze($e,['role'=>'admin']);footer_page();$html=ob_get_clean();
check(str_contains($html,'&lt;script&gt;')&&!str_contains($html,'Bench Pi <script>'),'component name escaped');
check(str_contains($html,'Last game result')&&!str_contains($html,'Key objective steps completed'),'finished view avoids reset-progress confusion');
check(str_contains($html,'What do the test games tell us?')&&str_contains($html,'Recent test games'),'sections rendered');
check(str_contains($html,'viewBox="0 0 900 210"')&&!str_contains($html,'style="height:'),'chart needs no inline styles');
file_put_contents('/preview.html',$html);
// Existing renderer still limits detailed telemetry on shared/basic views.
ob_start();render_exhibit($e,false,true,null);$basic=ob_get_clean();check(!str_contains($basic,'What do the test games tell us?'),'basic/shared permissions unchanged');
echo $passed." Maze checks passed\n";
