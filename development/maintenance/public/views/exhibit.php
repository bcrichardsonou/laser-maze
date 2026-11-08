<?php
require_once dirname(__DIR__).'/maintenance-lib.php';
require_once __DIR__.'/dashboard.php';
require_once __DIR__.'/remote-access.php';
require_once __DIR__.'/exhibit-layout.php';
function render_exhibit(array $e,bool $detail,bool $shared=false,?array $viewer=null): void {
    if ($shared) {$detail=false;$viewer=null;}
    if (preg_match('/^laser\s*maze$/i',trim($e['name']))) {require_once __DIR__.'/laser-maze.php';render_laser_maze($e,$viewer,$detail);return;}
    $eid=(int)$e['id'];$cs=components($eid);$booth=false;
    foreach($cs as $c)if(isset(dashboard_payload($c)['metrics']['booth_software_version']) && !dashboard_simulated($c))$booth=true;
    $stats=$booth?dashboard_counts($eid,$e['timezone']):null;
    echo '<section class="page-hero"><div class="eyebrow">'.esc($e['museum_name'].' · '.$e['location_name']).'</div><h1>'.esc($e['name']).'</h1><p>Connection, activity, and equipment conditions.</p></section>';
    exhibit_navigation($eid,$detail,$viewer);
    exhibit_section_start($eid,'overview','Overview');
    if($stats){echo '<div class="stats-grid">';dashboard_stat('Sessions completed today',$stats['today']['session_completed'] ?? 0,'Recorded completions');dashboard_stat('Print jobs submitted',$stats['today']['print_submitted'] ?? 0,'Today · physical output unconfirmed');dashboard_stat('GIFs created',$stats['today']['gif_created'] ?? 0,'Today · successfully generated');dashboard_stat('Emails accepted',$stats['today']['email_accepted'] ?? 0,'Today · inbox delivery unconfirmed');echo '</div>';}
    else echo '<p>Activity summaries will appear when this exhibit reports supported usage events.</p>';
    exhibit_viewing_links($e,$viewer);exhibit_section_end();
    exhibit_section_start($eid,'activity','Activity & outcomes');
    if($stats){dashboard_chart($stats['days']);dashboard_today($eid,$e['timezone']);dashboard_activity($stats,$e['timezone']);dashboard_reliability($stats);}else echo '<p>No supported activity measurements yet. Connection reports alone do not measure usage.</p>';
    exhibit_section_end();exhibit_section_start($eid,'equipment','Equipment & components');
    if($booth)dashboard_workflows($cs);
    echo '<div class="grid component-grid">';$found=false;
    foreach($cs as $c){if(!$c['active'])continue;$found=true;$live=fresh($c);$payload=dashboard_payload($c);$metrics=$payload['metrics'] ?? [];
        echo '<article class="card"><h3>'.esc($c['name']).'</h3>'.dashboard_condition($c['state'],$live).'<p>'.($live?'Reporting recently':'Connection unavailable / awaiting report').'</p><small>Last heartbeat: '.esc(stamp($c['last_contact'],$e['timezone'])).'</small>';
        if(!$live)echo '<p class="alert">Current equipment condition is unconfirmed.</p>';
        if(dashboard_simulated($c))echo '<p class="alert">Simulator data · excluded from activity totals.</p>';
        if($detail){if(!empty($payload['fault_summary']))echo '<p class="fault-note">'.esc($payload['fault_summary']).'</p>';echo '<details><summary>Reported component details</summary>';foreach($metrics as $key=>$value)echo '<div class="metric"><span>'.esc(dashboard_metric_label($key)).'</span><strong>'.esc(dashboard_metric_value($key,$value)).'</strong></div>';echo '<small>Device identity: '.esc($c['device_id']).'</small></details>';exhibit_component_software($c,$viewer);}
        echo '</article>';
    }echo '</div>';if(!$found)echo '<p>Awaiting component setup.</p>';exhibit_section_end();
    render_maintenance($e,$cs,$viewer);exhibit_section_start($eid,'history','Recent history');if($stats)dashboard_chart($stats['days']);else echo '<p>No supported activity history yet.</p>';echo '<p class="fine muted">Consolidated recent activity. Detailed event records are available to authorized staff.</p>';exhibit_section_end();
    if(($viewer['role'] ?? '')==='admin'){exhibit_section_start($eid,'access','Remote access',false);render_remote_access($cs,$viewer);exhibit_section_end();}
    if($detail){exhibit_section_start($eid,'technical','Technical details',false);dashboard_events($eid,$e['timezone']);render_retired_components($cs,$e['timezone']);exhibit_section_end();}
}

function render_retired_components(array $cs,string $zone): void {
    $retired=array_filter($cs,fn($c)=>!$c['active']);
    if (!$retired) return;
    echo '<details class="panel"><summary><strong>Retired components ('.count($retired).')</strong></summary><p class="muted fine">Archived records only. These components are not monitored for current condition. Their logs and recorded totals are preserved.</p>';
    foreach ($retired as $c) {
        echo '<details class="component-id"><summary>'.esc($c['name']).' — Retired</summary><p class="muted fine">Last recorded condition: '.esc(str_replace('_',' ',$c['state'])).'<br>Last heartbeat: '.esc(stamp($c['last_contact'],$zone)).'<br>Condition recorded: '.esc(stamp($c['state_at'],$zone)).'</p>';
        $payload=dashboard_payload($c);$metrics=$payload['metrics'] ?? [];
        if (dashboard_simulated($c)) echo '<p class="muted fine">Historical simulator data · excluded from activity totals.</p>';
        if (!empty($payload['fault_summary'])) echo '<p class="muted fine">Historical fault summary: '.esc($payload['fault_summary']).'</p>';
        if (is_array($metrics)) foreach ($metrics as $key=>$value) echo '<div class="metric"><span>'.esc(dashboard_metric_label($key)).'</span><strong>'.esc(dashboard_metric_value($key,$value)).'</strong></div>';
        echo '<p class="muted fine">Device: '.esc($c['device_id']).'</p></details>';
    }
    echo '</details>';
}
