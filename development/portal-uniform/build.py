from pathlib import Path
import json, hashlib
root=Path(__file__).parent
ref=root/'live-reference'; out=root/'update'
def patch(s,a,b):
    assert s.count(a)==1, (a[:100],s.count(a))
    return s.replace(a,b)
def write(name,s):
    p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)

lib=(ref/'lib.php').read_text()
lib=patch(lib,"style-src 'self'; img-src", "style-src 'self'; script-src 'self'; img-src")
lib=patch(lib,'<link rel="stylesheet" href="/assets/portal.css">','<link rel="stylesheet" href="/assets/portal.css"><link rel="stylesheet" href="/assets/exhibit-layout.css"><script src="/assets/exhibit-layout.js" defer></script>')
write('lib.php',lib)
index=(ref/'index.php').read_text()
old="elseif ($action==='exhibit') { $lid=id_input('location_id'); location_row($lid); q('INSERT INTO zp_exhibits(location_id,name) VALUES (?,?)',[$lid,text_input('name')]); }"
new="""elseif ($action==='exhibit') {
            $lid=id_input('location_id'); location_row($lid);$name=text_input('name');
            db()->beginTransaction();
            try {q('INSERT INTO zp_exhibits(location_id,name) VALUES (?,?)',[$lid,$name]);$eid=(int)db()->lastInsertId();
                $generated=exhibit_share_create($eid,null,$name);db()->commit();
            } catch(Throwable $error){db()->rollBack();throw $error;}
        }"""
index=patch(index,old,new)
index=patch(index,"$token=bin2hex(random_bytes(32)); q('INSERT INTO zp_shares(exhibit_id,location_id,token_hash,label) VALUES (?,?,?,?)',[$eid,$lid,hash('sha256',$token),text_input('label')]);\n            $generated=rtrim(cfg()['base_url'],'/').'/share.php?token='.$token;", "db()->beginTransaction();try {$generated=exhibit_share_create($eid,$lid,text_input('label'));db()->commit();}catch(Throwable $error){db()->rollBack();throw $error;}")
write('index.php',index)
admin=(ref/'views/admin.php').read_text()
admin=patch(admin,"esc($s['exhibit'] ?? $s['location']).'</td><td>';form_start('revoke-share');", "esc($s['exhibit'] ?? $s['location']).'</td><td>'; $view=exhibit_share_url($s);if($view)echo '<p><a href=\"'.esc($view).'\">Open viewing link</a><br><code>'.esc($view).'</code></p>';else echo '<p>Existing link preserved. Use your saved URL.</p>';form_start('revoke-share');")
write('views/admin.php',admin)

# Laser-specific measurements retained; layout, private details and sharing standardized.
maze=(ref/'views/laser-maze.php').read_text()
maze=patch(maze,'function render_laser_maze(array $e,?array $viewer): void {','function render_laser_maze(array $e,?array $viewer,bool $detail=true): void {')
start=maze.index("    echo '<nav class=\"maze-jump\"")
end=maze.index("    if ($s['limited'])",start)
maze=maze[:start]+"    exhibit_navigation($eid,$detail,$viewer);\n    if ($detail) {\n"+maze[start:end].split('\n',1)[1]+"    }\n"+maze[end:]
maze=patch(maze,"    echo '<section id=\"maze-now\"", "    exhibit_section_start($eid,'overview','Overview');\n    echo '<section id=\"maze-now\"")
maze=patch(maze,"        echo '<div class=\"maze-beams\">';", "        if ($detail) {echo '<div class=\"maze-beams\">';")
maze=patch(maze,"    }echo '</section>';", "        }\n    }echo '</section>';exhibit_viewing_links($e,$viewer);exhibit_section_end();")
maze=patch(maze,"    echo '<section id=\"maze-results\"", "    exhibit_section_start($eid,'activity','Activity & outcomes');\n    echo '<section id=\"maze-results\"")
maze=patch(maze,"    echo '<section id=\"maze-health\"", "    exhibit_section_end();exhibit_section_start($eid,'equipment','Equipment & components');\n    echo '<section id=\"maze-health\"")
maze=patch(maze,"        foreach(['arduino_connected'", "        if ($detail) foreach(['arduino_connected'")
maze=patch(maze,"        echo '<details><summary>Other reported metrics</summary>';foreach($values as $key=>$value)echo '<div class=\"metric\"><span>'.esc(dashboard_metric_label($key)).'</span><strong>'.esc(dashboard_metric_value($key,$value)).'</strong></div>';echo '</details></article>';}", "        if ($detail) {echo '<details><summary>Other reported metrics</summary>';foreach($values as $key=>$value)echo '<div class=\"metric\"><span>'.esc(dashboard_metric_label($key)).'</span><strong>'.esc(dashboard_metric_value($key,$value)).'</strong></div>';echo '</details>';exhibit_component_software($component,$viewer);}echo '</article>';}")
maze=patch(maze,"    echo '<section id=\"maze-history\"", "    exhibit_section_end();exhibit_section_start($eid,'history','Recent history');\n    if ($detail) {\n    echo '<section id=\"maze-history\"")
maze=patch(maze,"    render_remote_access($cs,$viewer);echo '<details class=\"panel\"><summary>Technical event history</summary>';dashboard_events($eid,$e['timezone']);echo '</details>';render_retired_components($cs,$e['timezone']);echo '</div>';", """    } else {echo '<p>Daily game starts and recorded outcomes in this view.</p>';maze_chart($s['days']);}
    exhibit_section_end();
    if (($viewer['role'] ?? '')==='admin') {exhibit_section_start($eid,'access','Remote access',false);render_remote_access($cs,$viewer);exhibit_section_end();}
    if ($detail) {exhibit_section_start($eid,'technical','Technical details',false);dashboard_events($eid,$e['timezone']);render_retired_components($cs,$e['timezone']);exhibit_section_end();}echo '</div>';""")
maze=patch(maze,"if (!empty(dashboard_payload($c)['fault_summary']))","if ($detail && !empty(dashboard_payload($c)['fault_summary']))")
write('views/laser-maze.php',maze)

exhibit=(ref/'views/exhibit.php').read_text(); retired=exhibit[exhibit.index('function render_retired_components'):]
write('views/exhibit.php', '''<?php
require_once __DIR__.'/dashboard.php';
require_once __DIR__.'/remote-access.php';
require_once __DIR__.'/exhibit-layout.php';
function render_exhibit(array $e,bool $detail,bool $shared=false,?array $viewer=null): void {
    if ($shared) {$detail=false;$viewer=null;}
    if (preg_match('/^laser\\s*maze$/i',trim($e['name']))) {require_once __DIR__.'/laser-maze.php';render_laser_maze($e,$viewer,$detail);return;}
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
    exhibit_section_start($eid,'history','Recent history');if($stats)dashboard_chart($stats['days']);else echo '<p>No supported activity history yet.</p>';echo '<p class="fine muted">Consolidated recent activity. Detailed event records are available to authorized staff.</p>';exhibit_section_end();
    if(($viewer['role'] ?? '')==='admin'){exhibit_section_start($eid,'access','Remote access',false);render_remote_access($cs,$viewer);exhibit_section_end();}
    if($detail){exhibit_section_start($eid,'technical','Technical details',false);dashboard_events($eid,$e['timezone']);render_retired_components($cs,$e['timezone']);exhibit_section_end();}
}

'''+retired)

# Replace inline-style charts with SVG so the existing CSP remains effective.
dash=(ref/'views/dashboard.php').read_text()
a=dash.index('function dashboard_chart(');b=dash.index('function dashboard_activity(',a)
dash=dash[:a]+'''function dashboard_chart(array $days): void {
    echo '<section class="panel"><h2>Activity over time · last 7 days</h2>';
    exhibit_svg_bars($days,'sessions','prints','Sessions completed','Print jobs submitted');
    echo '<p class="fine muted">Local dates at recording time. Queued uploads can leave totals incomplete.</p></section>';
}
function exhibit_svg_bars(array $days,string $one,string $two,string $labelOne,string $labelTwo): void {
    $max=1;foreach($days as $d)$max=max($max,$d[$one],$d[$two]);$step=900/max(1,count($days));
    echo '<svg class="exhibit-chart" viewBox="0 0 900 200" role="img" aria-label="'.esc($labelOne.' and '.$labelTwo).'"><title>'.esc($labelOne.' and '.$labelTwo).'</title>';
    $i=0;foreach($days as $day=>$d){$x=$i++*$step;$w=min(25,$step*.3);foreach([[$one,'series-one',-$w],[$two,'series-two',1]] as [$key,$class,$offset]){$h=$d[$key]/$max*150;echo '<rect class="'.$class.'" x="'.round($x+$step/2+$offset,2).'" y="'.round(160-$h,2).'" width="'.round($w,2).'" height="'.round($h,2).'"><title>'.esc($day.': '.$d[$key].' '.($key===$one?$labelOne:$labelTwo)).'</title></rect>';}echo '<text x="'.round($x+$step/2,2).'" y="185" text-anchor="middle">'.esc((new DateTimeImmutable($day))->format('M j')).'</text>';}
    echo '</svg><p>Orange: '.esc($labelOne).' · Blue: '.esc($labelTwo).'</p><details><summary>Exact daily counts</summary><div class="table-wrap"><table><tr><th>Date</th><th>'.esc($labelOne).'</th><th>'.esc($labelTwo).'</th></tr>';foreach($days as $day=>$d)echo '<tr><td>'.esc($day).'</td><td>'.$d[$one].'</td><td>'.$d[$two].'</td></tr>';echo '</table></div></details>';
}
'''+dash[b:]
a=dash.index("    foreach ($hours as $hour=>$count) echo")
b=dash.index("    echo '</div></div><div class=",a)
dash=dash[:a]+'''    foreach ($hours as $hour=>$count) echo '<div class="hour-column"><svg viewBox="0 0 20 100" role="img" aria-label="'.sprintf('%02d:00',$hour).': '.$count.' starts"><rect fill="#ec762e" x="0" y="'.round(100-$count/$max*100,2).'" width="20" height="'.round($count/$max*100,2).'"/></svg><small>'.sprintf('%02d',$hour).'</small></div>';
'''+dash[b:]
write('views/dashboard.php',dash)

# Paginated, component/exhibit filtered central archive library.
releases=(ref/'releases.php').read_text()
a=releases.index("$devices=q(");b=releases.index('foreach($devices as $c)',a)
releases=releases[:a]+'''$cid=filter_var($_GET['component'] ?? 0,FILTER_VALIDATE_INT) ?: 0;
$eid=filter_var($_GET['exhibit'] ?? 0,FILTER_VALIDATE_INT) ?: 0;
$page=max(1,min(10000,filter_var($_GET['p'] ?? 1,FILTER_VALIDATE_INT) ?: 1));$offset=($page-1)*10;
echo '<form method="get"><label>Exhibit<select name="exhibit"><option value="0">All exhibits</option>';foreach(q('SELECT id,name FROM zp_exhibits ORDER BY name') as $e)echo '<option value="'.(int)$e['id'].'"'.($eid===(int)$e['id']?' selected':'').'>'.esc($e['name']).'</option>';echo '</select></label><button>Filter library</button></form>';
$devices=q('SELECT c.*,e.name exhibit FROM zp_components c JOIN zp_exhibits e ON e.id=c.exhibit_id WHERE (?=0 OR c.id=?) AND (?=0 OR e.id=?) AND EXISTS (SELECT 1 FROM zp_releases r WHERE r.component_id=c.id) ORDER BY e.name,c.name LIMIT 10 OFFSET '.$offset,[$cid,$cid,$eid,$eid])->fetchAll();
'''+releases[b:]
releases=patch(releases,"    if (!$rs) continue;","    // Archive and attempt lists paginate independently.")
# For a component view use archive pagination; fleet overview uses short summaries.
releases=patch(releases,"ORDER BY id DESC LIMIT 200',[$c['id']])", "ORDER BY id DESC LIMIT '.($cid?20:5).' OFFSET '.($cid?($page-1)*20:0),[$c['id']])")
releases=patch(releases,"LIMIT 10 OFFSET '.$offset", "LIMIT 10 OFFSET '.($cid?0:$offset)")
releases=patch(releases,"ORDER BY d.started_at DESC LIMIT 100',[$c['id']])", "ORDER BY d.started_at DESC LIMIT '.($cid?20:5).' OFFSET '.($cid?($page-1)*20:0),[$c['id']])")
releases=patch(releases,"    echo '</tbody></table></section>';", "    echo '</tbody></table><p><a href=\"/releases.php?component='.(int)$c['id'].'\">Browse component history</a></p></section>';")
releases=patch(releases,"footer_page();", "if($page>1)echo '<a class=\"button secondary\" href=\"/releases.php?component='.$cid.'&amp;exhibit='.$eid.'&amp;p='.($page-1).'\">Previous</a>';if($devices)echo '<a class=\"button secondary\" href=\"/releases.php?component='.$cid.'&amp;exhibit='.$eid.'&amp;p='.($page+1).'\">Next</a>';echo '<p>Page '.$page.'. Fleet view: up to 10 components and 5 recent records each. Component view: 20 archives and attempts per page.</p>';footer_page();")
write('releases.php',releases)
hashes={str(p.relative_to(ref)):hashlib.sha256(p.read_bytes()).hexdigest() for p in ref.rglob('*.php') if (out/p.relative_to(ref)).exists()}
(root/'expected.json').write_text(json.dumps(hashes,indent=2)+'\n')
print('Update built; guarded source hashes saved.')
