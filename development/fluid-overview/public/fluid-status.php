<?php
require __DIR__.'/lib.php';require_once __DIR__.'/maintenance-lib.php';require_once __DIR__.'/fluid-lib.php';
transport();cfg();header('Cache-Control: no-store, private');
if($_SERVER['REQUEST_METHOD']!=='GET')json_reply(405,['error'=>'GET required']);
ip_limit('fluid-status',120,60);
$cid=filter_var($_GET['component'] ?? null,FILTER_VALIDATE_INT);
if(!$cid||$cid<1)json_reply(404,['error'=>'Status unavailable']);
$c=one('SELECT c.*,e.location_id,e.active exhibit_active FROM zp_components c JOIN zp_exhibits e ON e.id=c.exhibit_id WHERE c.id=? AND c.active=1 AND e.active=1',[$cid]);
if(!$c)json_reply(404,['error'=>'Status unavailable']);
if(isset($_GET['token'])){
    $token=$_GET['token'];
    if(!is_string($token)||!preg_match('/^[a-f0-9]{64}$/D',$token))json_reply(404,['error'=>'Status unavailable']);
    $s=one('SELECT exhibit_id,location_id FROM zp_shares WHERE token_hash=? AND active=1',[hash('sha256',$token)]);
    if(!$s||!fluid_share_scope($s,$c))json_reply(404,['error'=>'Status unavailable']);
}else{
    session_boot();$u=user();
    if(!$u)json_reply(401,['error'=>'Sign in required']);
    if(!allowed($u,(int)$c['exhibit_id']))json_reply(404,['error'=>'Status unavailable']);
}
json_reply(200,fluid_summary($c));
