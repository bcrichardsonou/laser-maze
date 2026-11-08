<?php
require __DIR__.'/lib.php';require_once __DIR__.'/maintenance-lib.php';transport();cfg();
if($_SERVER['REQUEST_METHOD']!=='POST')json_reply(405,['error'=>'POST required']);
limit('maintenance:ip:'.($_SERVER['REMOTE_ADDR'] ?? ''),600,60);
$raw=file_get_contents('php://input',false,null,0,8193);if($raw===false||strlen($raw)>8192)json_reply(413,['error'=>'Request too large']);
$b=json_decode($raw,true);if(!is_array($b))json_reply(400,['error'=>'Invalid request']);$device=$b['device_id'] ?? null;$key=$_SERVER['HTTP_X_ZOCO_KEY'] ?? null;
if(!is_array($b)||!is_string($device)||!is_string($key))json_reply(400,['error'=>'Invalid request']);
$c=one('SELECT * FROM zp_components WHERE device_id=? AND active=1',[$device]);
if(!$c||!hash_equals($c['key_hash'],hash('sha256',$key)))json_reply(401,['error'=>'Unauthorized']);
$cid=(int)$c['id'];if(!maintenance_enabled($cid))json_reply(403,['error'=>'Maintenance not enabled']);limit('maintenance:component:'.$cid,100,60);
try{
    db()->beginTransaction();$active=one('SELECT active FROM zp_components WHERE id=? FOR UPDATE',[$cid]);if(!$active||!$active['active']){db()->rollBack();json_reply(401,['error'=>'Component retired']);}
    maintenance_expire($cid);
    if(($b['action'] ?? '')==='poll'){
        $rows=q("SELECT * FROM zp_commands WHERE component_id=? AND status IN ('requested','accepted') AND expires_at>UTC_TIMESTAMP() ORDER BY CASE WHEN action IN ('stop_game','stop_audio') THEN 0 ELSE 1 END,created_at LIMIT 10",[$cid])->fetchAll();$commands=[];
        foreach($rows as $r){if($r['status']==='requested')q("UPDATE zp_commands SET status='accepted',updated_at=UTC_TIMESTAMP() WHERE id=? AND component_id=?",[$r['id'],$cid]);$commands[]=['id'=>$r['id'],'device_id'=>$device,'action'=>$r['action'],'params'=>(object)json_decode($r['parameters'],true),'expires_at'=>(new DateTimeImmutable($r['expires_at'],new DateTimeZone('UTC')))->getTimestamp()];}
        db()->commit();json_reply(200,['commands'=>$commands]);
    }
    $r=$b['result'] ?? null;
    if(($b['action'] ?? '')!=='ack'||!is_array($r)||($r['device_id'] ?? null)!==$device||!is_string($r['id'] ?? null)||!preg_match('/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/D',$r['id'])||!in_array($r['status'] ?? '',['completed','failed','expired'],true)||!is_string($r['reason'] ?? null)||!preg_match('/^[a-zA-Z0-9_]{1,100}$/D',$r['reason'])||!is_int($r['executed_at'] ?? null)){db()->rollBack();json_reply(400,['error'=>'Invalid result']);}
    $row=one('SELECT * FROM zp_commands WHERE id=? AND component_id=? FOR UPDATE',[$r['id'],$cid]);if(!$row){db()->rollBack();json_reply(404,['error'=>'Unknown component command']);}
    $encoded=json_encode($r,JSON_THROW_ON_ERROR);
    if(strlen($encoded)>4096){db()->rollBack();json_reply(413,['error'=>'Result too large']);}
    if($row['result']!==null && json_decode($row['result'],true)!=$r){db()->rollBack();json_reply(409,['error'=>'Conflicting result']);}
    if($row['result']===null){
        $expires=(new DateTimeImmutable($row['expires_at'],new DateTimeZone('UTC')))->getTimestamp();
        $status=$r['status'];if($status==='completed'&&$r['executed_at']>$expires)$status='unconfirmed';
        q('UPDATE zp_commands SET status=?,result=?,updated_at=UTC_TIMESTAMP() WHERE id=? AND component_id=?',[$status,$encoded,$r['id'],$cid]);
        audit(null,'maintenance_result',['component_id'=>$cid,'command_id'=>$r['id'],'status'=>$status,'reason'=>$r['reason']]);
    }
    db()->commit();json_reply(200,['acknowledged'=>$r['id']]);
}catch(Throwable $e){if(db()->inTransaction())db()->rollBack();error_log('ZoCo maintenance API failure: '.get_class($e));json_reply(503,['error'=>'Maintenance delivery unavailable']);}
