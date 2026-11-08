<?php
// Deliberately narrow projection; never return raw maintenance telemetry publicly.
require_once __DIR__.'/maintenance-lib.php';
function fluid_share_scope(array $s,array $c): bool {
    if(!empty($s['exhibit_id']))return (int)$s['exhibit_id']>0&&(int)$s['exhibit_id']===(int)$c['exhibit_id'];
    return !empty($s['location_id'])&&(int)$s['location_id']>0&&(int)$s['location_id']===(int)$c['location_id'];
}
function fluid_summary(?array $c,?array $live=null): array {
    $base=['state'=>'unconfirmed','percent'=>null,'updated_at'=>null];
    if(!$c||empty($c['active']))return $base;
    $live=$live ?? maintenance_live((int)$c['id']);
    if(!$live||($live['connected'] ?? null)!==true||!is_int($live['sampled_at'] ?? null)||abs(time()-$live['sampled_at'])>10)return $base;
    $t=$live['tank_level'] ?? null;
    if(!is_array($t)||!is_int($t['raw'] ?? null)||$t['raw']<0||$t['raw']>1023)return $base;
    $base['updated_at']=$live['sampled_at'];
    if(in_array($t['state'] ?? '',['open_or_connected_to_5v','short_or_connected_to_ground'],true))return array_replace($base,['state'=>'check_sensor']);
    if(($t['state'] ?? '')==='uncalibrated')return array_replace($base,['state'=>'uncalibrated']);
    $v=$t['float_height_percent'] ?? null;
    if(($t['state'] ?? '')!=='reading'||!is_array($t['calibration'] ?? null)||(!is_int($v)&&!is_float($v))||!is_finite((float)$v)||$v<0||$v>100)return $base;
    return ['state'=>'reading','percent'=>round((float)$v,1),'updated_at'=>$live['sampled_at']];
}
function render_fluid_overview(?array $c,bool $admin): void {
    $p=fluid_summary($c);$known=$p['state']==='reading';$cid=(int)($c['id'] ?? 0);
    $labels=['reading'=>'Live reading','unconfirmed'=>'Unconfirmed','uncalibrated'=>'Calibration needed','check_sensor'=>'Check sensor'];
    $percent=$known?rtrim(rtrim(number_format($p['percent'],1,'.',''),'0'),'.'):null;
    // Preserve whole-number zero (number formatting above would otherwise trim it away).
    if($known&&$percent==='')$percent='0';
    echo '<section class="panel maze-fluid-card" data-fluid-component="'.$cid.'" data-fluid-state="'.esc($p['state']).'"><div class="maze-fluid-intro"><div class="eyebrow">Equipment supply</div><h2>Hazer fluid level</h2><span class="maze-fluid-status" data-fluid-status>'.esc($labels[$p['state']]).'</span></div>';
    echo '<div class="maze-fluid-tank" role="meter" aria-label="Estimated fluid level from calibrated float" aria-valuemin="0" aria-valuemax="100"'.($known?' aria-valuenow="'.esc((string)$p['percent']).'"':' aria-valuetext="Unconfirmed"').'><div data-fluid-fill style="height:'.($known?esc((string)$p['percent']):'0').'%"></div><span aria-hidden="true">E</span></div>';
    echo '<div class="maze-fluid-reading"><strong data-fluid-percent>'.($known?esc($percent).'%':'—').'</strong><p>Estimated from calibrated float position.</p><small data-fluid-updated>'.($p['updated_at']?'Latest reading received; refreshes automatically.':'Waiting for a fresh sender reading.').'</small><small>Low-fluid alerts and automatic cutoff are not enabled.</small></div>';
    if($admin)echo '<a class="button secondary maze-fluid-calibrate" href="#maintenance-tank-'.$cid.'">Calibrate sender</a>';
    echo '</section><script src="/assets/fluid-level.js?v=20261107-1" defer></script>';
}
