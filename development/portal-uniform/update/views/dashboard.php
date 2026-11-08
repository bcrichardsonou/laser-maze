<?php
// Presentation helpers only. Existing authentication, configuration and ingestion stay in lib.php.
function dashboard_payload(array $c): array {
    $p=json_decode($c['state_payload'] ?? '{}',true);
    return is_array($p)?$p:[];
}
function dashboard_simulated(array $c): bool {
    $m=dashboard_payload($c)['metrics'] ?? [];
    if (!is_array($m)) return false;
    return !empty($m['simulated']) || stripos((string)($m['software_version'] ?? ''),'simulator')!==false;
}
function dashboard_counts(int $eid,string $zone): array {
    $now=new DateTimeImmutable('now',new DateTimeZone($zone));
    $today=$now->format('Y-m-d');$month=$now->format('Y-m-01');
    $ids=[]; foreach (components($eid) as $c) if (!dashboard_simulated($c)) $ids[]=(int)$c['id'];
    $result=['today'=>[],'month'=>[],'total'=>[],'first'=>null,'days'=>[]];
    for ($i=6;$i>=0;$i--) $result['days'][$now->modify('-'.$i.' days')->format('Y-m-d')]=['sessions'=>0,'prints'=>0];
    if (!$ids) return $result;
    $marks=implode(',',array_fill(0,count($ids),'?'));
    $kinds=['session_started','session_completed','session_failed','photo_created','gif_created','print_requested','print_submitted','print_failed','email_requested','email_accepted','email_failed','fault_detected'];
    $kindMarks=implode(',',array_fill(0,count($kinds),'?'));
    $rows=q("SELECT kind,SUM(total) lifetime,SUM(CASE WHEN day=? THEN total ELSE 0 END) today_total,SUM(CASE WHEN day>=? AND day<=? THEN total ELSE 0 END) month_total,MIN(day) first_day FROM zp_daily WHERE component_id IN ($marks) AND kind IN ($kindMarks) AND day<=? GROUP BY kind",array_merge([$today,$month,$today],$ids,$kinds,[$today]));
    foreach ($rows as $r) {
        $result['today'][$r['kind']]=(int)$r['today_total'];$result['month'][$r['kind']]=(int)$r['month_total'];$result['total'][$r['kind']]=(int)$r['lifetime'];
        if ($result['first']===null || $r['first_day']<$result['first']) $result['first']=$r['first_day'];
    }
    $rows=q("SELECT day,kind,SUM(total) amount FROM zp_daily WHERE component_id IN ($marks) AND day>=? AND day<=? AND kind IN ('session_completed','print_submitted') GROUP BY day,kind ORDER BY day",array_merge($ids,[array_key_first($result['days']),$today]));
    foreach ($rows as $r) if (isset($result['days'][$r['day']])) $result['days'][$r['day']][$r['kind']==='session_completed'?'sessions':'prints']=(int)$r['amount'];
    return $result;
}
function dashboard_stat(string $title,$number,string $subtitle): void {
    echo '<article class="card stat"><div class="eyebrow">'.esc($title).'</div><strong>'.esc(is_int($number)?number_format($number):$number).'</strong><small>'.esc($subtitle).'</small></article>';
}
function dashboard_chart(array $days): void {
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
function dashboard_activity(array $stats,string $zone): void {
    echo '<section class="panel"><div class="section-head"><div><div class="eyebrow">Recorded activity</div><h2>Today, this month, and since monitoring began</h2></div></div><div class="table-wrap"><table><thead><tr><th>Activity</th><th>Today</th><th>This month</th><th>Recorded total</th></tr></thead><tbody>';
    foreach (['session_completed'=>'Sessions completed','photo_created'=>'Single photos created','gif_created'=>'GIFs created','print_submitted'=>'Print jobs submitted','email_accepted'=>'Emails accepted for sending','session_failed'=>'Failed sessions','print_failed'=>'Failed print submissions','email_failed'=>'Failed email attempts','fault_detected'=>'Reported faults'] as $kind=>$label) {
        echo '<tr><th scope="row">'.esc($label).'</th>';foreach (['today','month','total'] as $period) echo '<td class="count">'.number_format($stats[$period][$kind] ?? 0).'</td>';echo '</tr>';
    }
    echo '</tbody></table></div><p class="muted fine">'.($stats['first']?'First recorded activity: '.esc($stats['first']).'.':'No matching activity events have been recorded yet.').' Totals include retained history from replaced components, excluding labeled simulators. They do not include activity before reporting was installed. Timezone: '.esc($zone).'.</p><p class="muted fine">Submitted print jobs do not confirm physical printing. Email acceptance does not confirm inbox delivery. Zeros mean no recorded events, not proof that an exhibit was unused.</p></section>';
}
function dashboard_condition(string $state,bool $fresh=true): string {
    $labels=['ready'=>'Ready','running'=>'In use','faulted'=>'Faulted','maintenance'=>'Maintenance','intentionally_off'=>'Intentionally off','unknown'=>'Unknown'];
    return '<span class="badge '.esc($fresh?$state:'unknown').'">'.esc($fresh?($labels[$state] ?? 'Unknown'):'Unconfirmed').'</span>';
}
function dashboard_workflows(array $cs): void {
    foreach ($cs as $c) {
        if (!$c['active'] || dashboard_simulated($c)) continue;
        $m=dashboard_payload($c)['metrics'] ?? [];
        if (!is_array($m) || !isset($m['booth_software_version'])) continue;
        echo '<div class="workflow-grid">';
        foreach (['photo'=>'Photo booth','printer'=>'Printing station','email'=>'Email sending'] as $area=>$label) {
            echo '<section class="card workflow"><div class="section-head"><h2>'.esc($label).'</h2>'.dashboard_condition((string)($m[$area.'_condition'] ?? 'unknown'),fresh($c)).'</div><p>'.esc($c['name']).'</p><small>'.esc($area==='printer'?'Paper sensor: not monitored yet.':($area==='email'?'Acceptance is recorded; inbox delivery is unconfirmed.':'Condition reflects observed application activity.')).'</small></section>';
        } echo '</div>';
    }
}
function dashboard_metric_value(string $key,$value): string {
    if (is_bool($value)) return $value?'Yes':'No';
    if ($key==='temperature_c' && is_numeric($value)) return round((float)$value,1).' °C';
    if ($key==='free_storage_mb' && is_numeric($value)) return number_format((float)$value/1024,1).' GiB';
    if ($key==='uptime_seconds' && is_numeric($value)) { $hours=(int)floor((float)$value/3600);return intdiv($hours,24).'d '.($hours%24).'h'; }
    return is_scalar($value)?(string)$value:'Unavailable';
}
function dashboard_metric_label(string $key): string {
    $labels=['temperature_c'=>'Pi temperature','free_storage_mb'=>'Free storage','uptime_seconds'=>'System uptime','booth_ui_responsive'=>'Booth UI responding','booth_software_version'=>'Booth reporting version','software_version'=>'Monitoring version','printer_paper_status'=>'Printer paper status'];
    return $labels[$key] ?? ucfirst(str_replace('_',' ',$key));
}
function dashboard_events(int $eid,string $zone): void {
    $names=['session_started'=>'Session started','session_completed'=>'Session completed','session_failed'=>'Session failed','photo_captured'=>'Photo captured','photo_created'=>'Single photo created','gif_created'=>'GIF created','print_requested'=>'Print requested','print_submitted'=>'Print job submitted','print_failed'=>'Print submission failed','email_requested'=>'Email requested','email_accepted'=>'Email accepted for sending','email_failed'=>'Email sending failed','fault_detected'=>'Fault reported','fault_cleared'=>'Fault cleared','application_started'=>'Application started','application_stopped'=>'Application stopped','application_error'=>'Application error','condition_changed'=>'Condition changed','setup_test'=>'Setup connection test'];
    echo '<section class="panel"><div class="section-head"><div><div class="eyebrow">Event history</div><h2>Recent activity</h2></div><a class="button secondary" href="/?page=export&amp;id='.$eid.'">Download logs</a></div><div class="table-wrap"><table><thead><tr><th>Time</th><th>Component</th><th>Activity</th><th>Details</th></tr></thead><tbody>';
    $rows=q("SELECT v.*,c.name FROM zp_events v JOIN zp_components c ON c.id=v.component_id WHERE c.exhibit_id=? AND v.kind NOT IN ('heartbeat','status','photo_captured') ORDER BY v.occurred_at DESC LIMIT 100",[$eid]);$found=false;
    foreach ($rows as $r) {
        $found=true;$p=json_decode($r['payload'],true);$pieces=[];
        // Readable summaries use a small allowlist; raw records remain behind detailed access.
        foreach (['area','condition','reason','mode','photos_expected','photos_captured','frames','duration_seconds','error_type'] as $key) if (is_array($p) && isset($p[$key]) && is_scalar($p[$key])) $pieces[]=ucfirst(str_replace('_',' ',$key)).': '.$p[$key];
        if ($r['kind']==='email_accepted') $pieces[]='Inbox delivery unconfirmed';
        if ($r['kind']==='print_submitted') $pieces[]='Physical printing unconfirmed';
        echo '<tr><td>'.esc(stamp($r['occurred_at'],$zone)).'</td><td>'.esc($r['name']).'</td><td><strong>'.esc($names[$r['kind']] ?? ucfirst(str_replace('_',' ',$r['kind']))).'</strong></td><td>'.esc(implode(' · ',$pieces)).'<details><summary>Raw event</summary><pre>'.esc($r['payload']).'</pre></details></td></tr>';
    }
    if (!$found) echo '<tr><td colspan="4">No activity events recorded yet. Heartbeats, status reports, and individual captures are available in the log download.</td></tr>';
    echo '</tbody></table></div><p class="muted fine">Latest 100 activity events. Raw events are retained for 90 days; daily totals are retained separately.</p></section>';
}
function dashboard_reliability(array $stats): void {
    echo '<section class="panel"><div class="eyebrow">Recorded outcomes · since reporting began</div><h2>Workflow reliability</h2><p class="fine muted">Rates use completed and failed outcomes. Pending work is not counted.</p>';
    foreach ([['session_completed','session_failed','Sessions completed'],['print_submitted','print_failed','Print submissions accepted'],['email_accepted','email_failed','Email requests accepted']] as [$ok,$bad,$name]) {
        $good=$stats['total'][$ok] ?? 0;$failed=$stats['total'][$bad] ?? 0;$total=$good+$failed;$rate=$total?round($good/$total*100,1):null;
        echo '<div class="reliability-row"><div><strong>'.esc($name).'</strong><small>'.number_format($good).' completed / accepted · '.number_format($failed).' failed</small></div><strong>'.($rate===null?'No outcomes':$rate.'%').'</strong></div>';
        if ($rate!==null) echo '<meter min="0" max="100" value="'.$rate.'" aria-label="'.esc($name).' percentage">'.$rate.'%</meter>';
    }
    echo '<p class="fine muted">Print and email rates measure software outcomes, not physical printing or inbox delivery. Repeated email attempts are counted separately.</p></section>';
}
function dashboard_today(int $eid,string $zone): void {
    $now=new DateTimeImmutable('now',new DateTimeZone($zone));$start=$now->setTime(0,0);$end=$start->modify('+1 day');$utc=new DateTimeZone('UTC');
    $hours=array_fill(0,24,0);$modes=['photo'=>0,'gif'=>0];$durations=[];$n=0;
    $rows=q("SELECT v.kind,v.occurred_at,v.payload,c.state_payload FROM zp_events v JOIN zp_components c ON c.id=v.component_id WHERE c.exhibit_id=? AND v.occurred_at>=? AND v.occurred_at<? AND v.kind IN ('session_started','session_completed') ORDER BY v.occurred_at LIMIT 10000",[$eid,$start->setTimezone($utc)->format('Y-m-d H:i:s.u'),$end->setTimezone($utc)->format('Y-m-d H:i:s.u')]);
    foreach ($rows as $r) {
        $n++;if (dashboard_simulated($r)) continue;$payload=json_decode($r['payload'],true);if (!is_array($payload)) continue;
        if ($r['kind']==='session_started') {
            $hour=(int)(new DateTimeImmutable($r['occurred_at'],$utc))->setTimezone(new DateTimeZone($zone))->format('G');$hours[$hour]++;
            if (is_string($payload['mode'] ?? null) && isset($modes[$payload['mode']])) $modes[$payload['mode']]++;
        } elseif (isset($payload['duration_seconds']) && is_numeric($payload['duration_seconds']) && is_finite((float)$payload['duration_seconds']) && $payload['duration_seconds']>=0) $durations[]=(float)$payload['duration_seconds'];
    }
    echo '<section class="panel"><div class="section-head"><div><div class="eyebrow">Today · '.esc($zone).'</div><h2>When visitors start sessions</h2></div></div><div class="hour-scroll"><div class="hour-chart">';$max=max(1,max($hours));
    foreach ($hours as $hour=>$count) echo '<div class="hour-column"><svg viewBox="0 0 20 100" role="img" aria-label="'.sprintf('%02d:00',$hour).': '.$count.' starts"><rect fill="#ec762e" x="0" y="'.round(100-$count/$max*100,2).'" width="20" height="'.round($count/$max*100,2).'"/></svg><small>'.sprintf('%02d',$hour).'</small></div>';
    echo '</div></div><div class="today-insights"><div><span class="eyebrow">Single-photo starts</span><strong>'.number_format($modes['photo']).'</strong></div><div><span class="eyebrow">GIF session starts</span><strong>'.number_format($modes['gif']).'</strong></div><div><span class="eyebrow">Average completed session</span><strong>'.($durations?number_format(array_sum($durations)/count($durations),1).' sec':'Not recorded').'</strong><small>'.count($durations).' timed completions today</small></div></div><p class="fine muted">Session duration includes capture, processing, and entry into the result view; it excludes email sending. '.($n>=10000?'This view is limited to the earliest 10,000 matching events today.':'Based on today’s recorded session events.').'</p></section>';
}
