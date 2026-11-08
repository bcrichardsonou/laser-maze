<?php
// Laser Maze detailed dashboard. Authentication remains in the existing router.
function maze_mode(string $mode): string {
    return ['usb'=>'USB objective','usb-break-all'=>'USB · break all beams','keys'=>'Key sequence','keys-break-all'=>'Keys · break all beams'][$mode] ?? 'Unknown mode';
}
function maze_outcome(string $outcome): string {
    return ['win'=>'Won','beam_limit'=>'Third beam break','timeout'=>'Time expired','stopped'=>'Operator stopped','startup_blocked'=>'Blocked at startup','communication_fault'=>'Controller connection lost','interrupted'=>'Interrupted / restart'][$outcome] ?? 'Other result';
}
function maze_settings(): array {
    $days=filter_var($_GET['maze_days'] ?? 7,FILTER_VALIDATE_INT);
    if (!in_array($days,[7,30,90],true)) $days=7;
    $timing=$_GET['maze_timing'] ?? 'all';
    if (!is_string($timing) || !in_array($timing,['all','fast','normal'],true)) $timing='all';
    return [$days,$timing];
}
function maze_stats(array $rows,string $zone,int $days,string $timing,?DateTimeImmutable $now=null): array {
    $tz=new DateTimeZone($zone);$now=($now ?? new DateTimeImmutable('now',$tz))->setTimezone($tz);
    $today=$now->format('Y-m-d');$s=['today_starts'=>0,'starts'=>0,'results'=>0,'wins'=>0,'challenge_results'=>0,'break_total'=>0,'break_samples'=>0,'days'=>[],'modes'=>[],'outcomes'=>[],'sessions'=>[],'faults'=>[],'win_times'=>['fast'=>[],'normal'=>[]],'skipped'=>0];
    for ($i=$days-1;$i>=0;$i--) $s['days'][$now->modify('-'.$i.' days')->format('Y-m-d')]=['starts'=>0,'results'=>0];
    $seen=[];
    foreach ($rows as $r) {
        $p=json_decode($r['payload'],true);
        if (!is_array($p) || ($p['bench_prototype'] ?? null)!==true) continue;
        try {$date=new DateTimeImmutable($r['occurred_at'],new DateTimeZone('UTC'));}catch(Throwable $e){$s['skipped']++;continue;}
        $day=$date->setTimezone($tz)->format('Y-m-d');if (!isset($s['days'][$day])) continue;
        if ($r['kind']==='bench_controller_fault') {$s['faults'][]=$r;continue;}
        if (!is_bool($p['fast_demo'] ?? null) || !is_string($p['mode'] ?? null) ||
            !in_array($p['mode'],['usb','usb-break-all','keys','keys-break-all'],true) ||
            !is_string($p['session_id'] ?? null) || !preg_match('/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/D',$p['session_id'])) {$s['skipped']++;continue;}
        $profile=$p['fast_demo']?'fast':'normal';if ($timing!=='all' && $profile!==$timing) continue;
        $identity=$r['component_id'].':'.$p['session_id'];$key=$identity.':'.$r['kind'];
        if (isset($seen[$key])) continue;$seen[$key]=true;
        $group=$p['mode'].':'.$profile;
        if (!isset($s['modes'][$group])) $s['modes'][$group]=['mode'=>$p['mode'],'profile'=>$profile,'starts'=>0,'results'=>0,'wins'=>0,'challenge_results'=>0];
        if (!isset($s['sessions'][$identity])) $s['sessions'][$identity]=['component'=>$r['name'],'time'=>$r['occurred_at'],'mode'=>$p['mode'],'profile'=>$profile,'start'=>null,'result'=>null];
        $row=&$s['sessions'][$identity];if ($r['occurred_at']>$row['time']) $row['time']=$r['occurred_at'];
        if ($r['kind']==='bench_game_started') {
            $s['starts']++;$s['modes'][$group]['starts']++;$s['days'][$day]['starts']++;
            if ($day===$today) $s['today_starts']++;$row['start']=$p;
        } elseif ($r['kind']==='bench_game_result') {
            $outcome=$p['outcome'] ?? null;
            if (!is_string($outcome)) {$s['skipped']++;unset($row);continue;}
            $s['results']++;$s['modes'][$group]['results']++;$s['days'][$day]['results']++;
            $s['outcomes'][$outcome]=($s['outcomes'][$outcome] ?? 0)+1;$row['result']=$p;
            if (in_array($outcome,['win','beam_limit','timeout'],true)) {$s['challenge_results']++;$s['modes'][$group]['challenge_results']++;}
            if ($outcome==='win') {$s['wins']++;$s['modes'][$group]['wins']++;}
            if (in_array($outcome,['win','beam_limit','timeout'],true) && is_numeric($p['break_count'] ?? null) && $p['break_count']>=0) {$s['break_total']+=(int)$p['break_count'];$s['break_samples']++;}
            $seconds=$p['elapsed_seconds'] ?? null;
            if ($outcome==='win' && (is_int($seconds)||is_float($seconds)) && is_finite((float)$seconds) && $seconds>=0 && $seconds<=600) $s['win_times'][$profile][]=(float)$seconds;
        }
        unset($row);
    }
    uasort($s['sessions'],fn($a,$b)=>strcmp($b['time'],$a['time']));
    ksort($s['modes']);return $s;
}
function maze_read_stats(int $eid,string $zone,int $days,string $timing): array {
    $now=new DateTimeImmutable('now',new DateTimeZone($zone));$utc=new DateTimeZone('UTC');
    $start=$now->setTime(0,0)->modify('-'.($days-1).' days')->setTimezone($utc)->format('Y-m-d H:i:s.u');
    $end=$now->setTime(0,0)->modify('+1 day')->setTimezone($utc)->format('Y-m-d H:i:s.u');
    $rows=q("SELECT v.component_id,v.kind,v.occurred_at,v.payload,c.name FROM zp_events v JOIN zp_components c ON c.id=v.component_id WHERE c.exhibit_id=? AND v.occurred_at>=? AND v.occurred_at<? AND v.kind IN ('bench_game_started','bench_game_result','bench_controller_fault') ORDER BY v.occurred_at DESC LIMIT 20001",[$eid,$start,$end])->fetchAll();
    $limited=count($rows)>20000;$stats=maze_stats(array_slice($rows,0,20000),$zone,$days,$timing,$now);$stats['limited']=$limited;return $stats;
}
function maze_current(array $components): ?array {
    $eligible=array_filter($components,fn($c)=>$c['active'] && isset(dashboard_payload($c)['metrics']['game_phase']));
    usort($eligible,fn($a,$b)=>strcmp($b['state_at'] ?? '',$a['state_at'] ?? ''));return $eligible[0] ?? null;
}
function maze_live(array $c): bool {
    if (!fresh($c) || !$c['state_at']) return false;
    return time()-(new DateTimeImmutable($c['state_at'],new DateTimeZone('UTC')))->getTimestamp()<=120;
}
function maze_clock($seconds): string {
    if (!is_numeric($seconds) || !is_finite((float)$seconds) || $seconds<0) return 'Not reported';
    $n=(int)ceil($seconds);return sprintf('%02d:%02d',intdiv($n,60),$n%60);
}
function maze_metric(array $m,string $key,string $label,bool $live): void {
    echo '<div class="metric"><span>'.esc($label).'</span><strong>'.esc($live && array_key_exists($key,$m)?dashboard_metric_value($key,$m[$key]):'Unconfirmed').'</strong></div>';
}
function maze_chart(array $days): void {
    $width=900;$height=210;$count=count($days);$step=$width/max(1,$count);$max=1;
    foreach($days as $d)$max=max($max,$d['starts'],$d['results']);
    echo '<svg class="maze-chart" viewBox="0 0 '.$width.' '.$height.'" role="img" aria-label="Daily test starts and recorded results"><title>Daily starts and results; exact counts in the table below</title>';
    $i=0;foreach($days as $date=>$d){$x=$i*$step;$bar=max(1,min(28,$step*0.32));$h1=$d['starts']/$max*150;$h2=$d['results']/$max*150;
        echo '<g><title>'.esc($date.': '.$d['starts'].' starts, '.$d['results'].' results').'</title><rect class="maze-start-bar" x="'.round($x+$step/2-$bar,2).'" y="'.round(165-$h1,2).'" width="'.$bar.'" height="'.round($h1,2).'"/><rect class="maze-result-bar" x="'.round($x+$step/2+1,2).'" y="'.round(165-$h2,2).'" width="'.$bar.'" height="'.round($h2,2).'"/>';
        if ($count<=7 || $i%max(1,(int)ceil($count/7))===0)echo '<text x="'.round($x+$step/2,2).'" y="190" text-anchor="middle">'.esc((new DateTimeImmutable($date))->format('M j')).'</text>';echo '</g>';$i++;}
    echo '</svg><p class="fine muted">Orange: starts · Blue: recorded results. Results can arrive later than starts.</p><details><summary>Exact daily counts</summary><div class="table-wrap"><table><tr><th>Date</th><th>Starts</th><th>Results</th></tr>';
    foreach($days as $date=>$d)echo '<tr><td>'.esc($date).'</td><td>'.$d['starts'].'</td><td>'.$d['results'].'</td></tr>';echo '</table></div></details>';
}
function render_laser_maze(array $e,?array $viewer): void {
    $eid=(int)$e['id'];$cs=components($eid);[$days,$timing]=maze_settings();$s=maze_read_stats($eid,$e['timezone'],$days,$timing);
    echo '<link rel="stylesheet" href="/assets/laser-maze.css"><div class="maze-dashboard">';
    echo '<section class="page-hero"><div class="eyebrow">'.esc($e['museum_name'].' · '.$e['location_name']).'</div><h1>'.esc($e['name']).'</h1><p>Game outcomes, beam status, and equipment health.</p></section>';
    echo '<p class="maze-prototype"><strong>Bench prototype</strong> · Buttons simulate laser receivers and objectives. These are test sessions, not visitor counts.</p>';
    echo '<nav class="maze-jump" aria-label="Laser Maze sections"><a href="#maze-now">Right now</a><a href="#maze-results">Results &amp; trends</a><a href="#maze-health">Equipment</a><a href="#maze-history">Recent games</a></nav>';
    echo '<form method="get" class="maze-filters"><input type="hidden" name="page" value="exhibit"><input type="hidden" name="id" value="'.$eid.'"><label>History window<select name="maze_days">';
    foreach([7,30,90] as $n)echo '<option value="'.$n.'"'.($n===$days?' selected':'').'>Last '.$n.' days</option>';echo '</select></label><label>Test timing<select name="maze_timing">';
    foreach(['all'=>'All test timings','fast'=>'Fast demos only','normal'=>'Normal timing only'] as $v=>$label)echo '<option value="'.$v.'"'.($v===$timing?' selected':'').'>'.esc($label).'</option>';echo '</select></label><button>Apply filters</button></form>';
    if ($s['limited']) echo '<p class="alert">High activity: this view uses the latest 20,000 matching events. Totals and charts may be incomplete.</p>';
    if ($s['skipped']) echo '<p class="alert">'.(int)$s['skipped'].' incomplete records were excluded from analysis.</p>';
    echo '<section id="maze-now" class="panel"><div class="eyebrow">Most recent report</div><h2>What is happening right now?</h2>';
    $c=maze_current($cs);$m=$c?(dashboard_payload($c)['metrics'] ?? []):[];$live=$c && maze_live($c) && ($m['game_phase'] ?? '')!=='stopped';
    if (!$c) echo '<p>Awaiting the first game status report. Connectivity reporting alone does not provide game progress.</p>';
    else {
        $phase=['idle'=>'Waiting for a game','starting'=>'Starting countdown','running'=>'Game in progress','finished'=>'Game ended','fault'=>'Needs attention','stopped'=>'Game program stopped'][$m['game_phase'] ?? ''] ?? 'Unknown game phase';
        echo '<div class="maze-now-grid"><div><h3>'.esc($live?$phase:'Current game unconfirmed').'</h3>'.dashboard_condition($c['state'],(bool)$live).'<p>'.esc($c['name']).'</p><small>Snapshot: '.esc(stamp($c['state_at'],$e['timezone'])).'</small></div><div><span class="eyebrow">Time remaining · snapshot</span><strong class="maze-timer">'.esc($live?maze_clock($m['remaining_seconds'] ?? null):'—').'</strong><small>'.esc(isset($m['fast_demo'])?($m['fast_demo']?'Fast demo timing':'Normal game timing'):'Timing unreported').'</small></div><div>';
        echo '<p><strong>Mode:</strong> '.esc($live?maze_mode((string)($m['game_mode'] ?? '')):'Unconfirmed').'</p>';
        maze_metric($m,'break_count',($m['game_phase'] ?? '')==='finished'?'Breaks in last game':'Breaks this game',(bool)$live);
        if (in_array($m['game_phase'] ?? '',['starting','running'],true)) {
            maze_metric($m,'key_progress','Key objective steps completed',(bool)$live);maze_metric($m,'objective_completed','Objective completed',(bool)$live);
        } elseif (isset($m['last_result'])) echo '<div class="metric"><span>Last game result</span><strong>'.esc($live?maze_outcome((string)$m['last_result']):'Unconfirmed').'</strong></div>';
        echo '</div></div>';
        if (!$live) echo '<p class="alert">'.(($m['game_phase'] ?? '')==='stopped'?'The game program is stopped. Live equipment state is unconfirmed.':'The last game report is stale or the component heartbeat is missing. Recorded values are not current.').'</p>';
        if (!empty(dashboard_payload($c)['fault_summary']))echo '<p class="fault-note">'.esc(str_replace('_',' ',dashboard_payload($c)['fault_summary'])).'</p>';
        echo '<div class="maze-beams">';
        for($i=1;$i<=2;$i++) {echo '<article class="card"><h3>Beam '.$i.'</h3>';maze_metric($m,'beam'.$i.'_input_active','Simulated receiver blocked',(bool)$live);maze_metric($m,'beam'.$i.'_commanded_on','Output requested on',(bool)$live);echo '<small>Button input and requested LED output; physical laser readiness is unmeasured.</small></article>';}
        echo '</div><p class="fine muted">Refresh for new reports. The countdown is the last reported value, not a live clock. History filters do not alter this current snapshot.</p>';
    }echo '</section>';
    echo '<section id="maze-results"><div class="section-head"><div><div class="eyebrow">Last '.$days.' days · '.esc($e['timezone']).'</div><h2>What do the test games tell us?</h2></div></div><div class="stats-grid">';
    dashboard_stat('Tests started today',$s['today_starts'],'Selected timing profile');dashboard_stat('Results recorded',$s['results'],'Within the selected history window');dashboard_stat('Games won',$s['wins'],'Test outcomes only');
    $rate=$s['challenge_results']?round($s['wins']/$s['challenge_results']*100,1).'%':'No outcomes';dashboard_stat('Challenge win rate',$rate,$s['challenge_results'].' wins + beam losses + timeouts');echo '</div>';
    echo '<section class="panel"><h2>Activity over time</h2>';maze_chart($s['days']);echo '</section>';
    echo '<div class="maze-two-column"><section class="panel"><h2>How games ended</h2><table><tr><th>Outcome</th><th>Count</th></tr>';
    foreach(['win','beam_limit','timeout','stopped','startup_blocked','communication_fault','interrupted'] as $outcome)echo '<tr><th>'.esc(maze_outcome($outcome)).'</th><td>'.number_format($s['outcomes'][$outcome] ?? 0).'</td></tr>';
    echo '</table><p class="fine muted">Beam losses and timeouts are normal challenge outcomes. Stops, startup blocks, connection faults, and interruptions are excluded from win rate.</p></section><section class="panel"><h2>Useful performance clues</h2>';
    foreach(['fast'=>'Fast demo wins','normal'=>'Normal timing wins'] as $profile=>$label){$values=$s['win_times'][$profile];echo '<div class="metric"><span>Average time · '.esc($label).'</span><strong>'.($values?number_format(array_sum($values)/count($values),1).' sec':'Not recorded').'</strong></div><small>'.count($values).' timed wins in this view</small>';}
    echo '<div class="metric"><span>Average breaks per resolved challenge</span><strong>'.($s['break_samples']?number_format($s['break_total']/$s['break_samples'],1):'Not recorded').'</strong></div><p class="fine muted">Running duration excludes startup. Fast and normal win times are kept separate. Different modes have different objectives and difficulty; these figures describe recorded tests rather than visitor difficulty.</p></section></div>';
    echo '<section class="panel"><h2>Which modes are being tested?</h2><div class="table-wrap"><table><tr><th>Mode</th><th>Timing</th><th>Starts</th><th>Results</th><th>Wins</th><th>Win rate</th></tr>';
    foreach($s['modes'] as $g)echo '<tr><th>'.esc(maze_mode($g['mode'])).'</th><td>'.($g['profile']==='fast'?'Fast demo':'Normal').'</td><td>'.$g['starts'].'</td><td>'.$g['results'].'</td><td>'.$g['wins'].'</td><td>'.($g['challenge_results']?round($g['wins']/$g['challenge_results']*100,1).'%':'No outcomes').'</td></tr>';
    if (!$s['modes'])echo '<tr><td colspan="6">No matching game reports yet. Run a game and allow queued uploads to arrive.</td></tr>';echo '</table></div></section></section>';
    echo '<section id="maze-health" class="panel"><h2>Equipment and reporting health</h2><p class="fine muted">Connection health is separate from game success. Unknown does not mean a confirmed hardware failure.</p><div class="maze-beams">';
    foreach($cs as $component){if(!$component['active'])continue;$values=dashboard_payload($component)['metrics'] ?? [];$current=maze_live($component)&&($values['game_phase'] ?? '')!=='stopped';echo '<article class="card"><h3>'.esc($component['name']).'</h3>'.dashboard_condition($component['state'],$current).'<p>Last heartbeat: '.esc(stamp($component['last_contact'],$e['timezone'])).'</p>';
        foreach(['arduino_connected'=>'Arduino responding','keypad_available'=>'Keypad responding','firmware_version'=>'Arduino firmware','python_version'=>'Game software','temperature_c'=>'Pi temperature','uptime_seconds'=>'Pi uptime'] as $key=>$label)maze_metric($values,$key,$label,$current);
        echo '<details><summary>Other reported metrics</summary>';foreach($values as $key=>$value)echo '<div class="metric"><span>'.esc(dashboard_metric_label($key)).'</span><strong>'.esc(dashboard_metric_value($key,$value)).'</strong></div>';echo '</details></article>';}
    echo '</div><p>Controller fault reports in this history window: <strong>'.count($s['faults']).'</strong></p><p class="fine muted">Fault reports are counted across all timing profiles. Missing reports or offline queues can leave history incomplete.</p></section>';
    echo '<section id="maze-history" class="panel"><div class="section-head"><h2>Recent test games</h2><a class="button secondary" href="/?page=export&amp;id='.$eid.'">Download logs</a></div><div class="table-wrap"><table><tr><th>Last activity</th><th>Mode / timing</th><th>Outcome</th><th>Running time</th><th>Breaks</th></tr>';
    foreach(array_slice($s['sessions'],0,30) as $session){$result=$session['result'];$duration=$result['elapsed_seconds'] ?? null;echo '<tr><td>'.esc(stamp($session['time'],$e['timezone'])).'<br><small>'.esc($session['component']).'</small></td><td>'.esc(maze_mode($session['mode'])).'<br><small>'.($session['profile']==='fast'?'Fast demo':'Normal timing').'</small></td><td>'.esc($result?maze_outcome((string)$result['outcome']):'No recorded result').'</td><td>'.esc(is_numeric($duration)?number_format((float)$duration,1).' sec':'Unconfirmed').'</td><td>'.esc(isset($result['break_count'])?$result['break_count']:'Unconfirmed').'</td></tr>';}
    if (!$s['sessions'])echo '<tr><td colspan="5">No matching sessions yet.</td></tr>';echo '</table></div><p class="fine muted">Latest 30 sessions in this view. “No recorded result” can mean a game is active, reporting is delayed, or the result lies outside the history window. Raw events are retained for 90 days; outcome analysis uses that retained history, not lifetime totals.</p></section>';
    render_remote_access($cs,$viewer);echo '<details class="panel"><summary>Technical event history</summary>';dashboard_events($eid,$e['timezone']);echo '</details>';render_retired_components($cs,$e['timezone']);echo '</div>';
}
