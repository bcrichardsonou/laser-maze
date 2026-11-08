<?php
// Shared presentation contract for current and future exhibit dashboards.
function exhibit_section_start(int $eid,string $key,string $title,bool $open=true): void {
    echo '<details class="exhibit-section panel" id="exhibit-'.$eid.'-'.esc($key).'" data-section="'.esc($key).'"'.($open?' open':'').'><summary><strong>'.esc($title).'</strong></summary><div class="exhibit-section-body">';
}
function exhibit_section_end(): void {echo '</div></details>';}
function exhibit_navigation(int $eid,bool $detail,?array $viewer): void {
    $sections=['overview'=>'Overview','activity'=>'Activity & outcomes','equipment'=>'Equipment & components'];
    if (($viewer['role'] ?? '')==='admin') $sections['maintenance']='Maintenance';
    $sections['history']='Recent history';
    if (($viewer['role'] ?? '')==='admin') $sections['access']='Remote access';
    if ($detail) $sections['technical']='Technical details';
    echo '<nav class="exhibit-jump" aria-label="Exhibit sections">';
    foreach($sections as $key=>$title)echo '<a class="button secondary" href="#exhibit-'.$eid.'-'.$key.'">'.esc($title).'</a>';
    echo '</nav>';
}
function exhibit_share_create(?int $eid,?int $lid,string $label): string {
    $token=bin2hex(random_bytes(32));
    q('INSERT INTO zp_shares(exhibit_id,location_id,token_hash,label) VALUES (?,?,?,?)',[$eid,$lid,hash('sha256',$token),$label]);
    $id=(int)db()->lastInsertId();
    q('INSERT INTO zp_settings(name,value) VALUES (?,?)',['viewing_link:'.$id,seal($token)]);
    return rtrim(cfg()['base_url'],'/').'/share.php?token='.$token;
}
function exhibit_share_url(array $s): ?string {
    if (!$s['active']) return null;
    $r=one('SELECT value FROM zp_settings WHERE name=?',['viewing_link:'.(int)$s['id']]);
    if (!$r) return null;
    $token=unseal($r['value']);
    if (!hash_equals($s['token_hash'],hash('sha256',$token))) return null;
    return rtrim(cfg()['base_url'],'/').'/share.php?token='.$token;
}
function exhibit_viewing_links(array $e,?array $viewer): void {
    if (($viewer['role'] ?? '')!=='admin') return;
    echo '<details class="panel"><summary>Exhibit viewing links</summary><p>Anyone with a link can view this exhibit’s summaries. Revoke links in Manage.</p>';
    $found=false;
    foreach(q('SELECT * FROM zp_shares WHERE exhibit_id=? AND active=1 ORDER BY id DESC',[$e['id']]) as $s){$found=true;$url=exhibit_share_url($s);echo '<p><strong>'.esc($s['label']).'</strong><br>'.($url?'<a href="'.esc($url).'">Open viewing page</a><br><code>'.esc($url).'</code>':'Existing link preserved; use your saved URL or create a replacement in Manage.').'</p>';}
    if (!$found)echo '<p>No active link. Create one in Manage; revoked links are never recreated automatically.</p>';
    echo '</details>';
}
function exhibit_component_software(array $c,?array $viewer): void {
    if (($viewer['role'] ?? '')!=='admin')return;
    $id=(int)$c['id'];
    echo '<details class="component-software"><summary>Software releases & deployment history</summary>';
    $last=one('SELECT d.*,r.version FROM zp_deployments d JOIN zp_releases r ON r.id=d.release_id AND r.component_id=d.component_id WHERE d.component_id=? ORDER BY d.started_at DESC,d.updated_at DESC LIMIT 1',[$id]);
    $verified=one("SELECT d.*,r.version FROM zp_deployments d JOIN zp_releases r ON r.id=d.release_id AND r.component_id=d.component_id WHERE d.component_id=? AND d.status='verified' ORDER BY d.started_at DESC LIMIT 1",[$id]);
    echo '<p>Latest verified deployment: <strong>'.esc($verified?$verified['version']:'None recorded').'</strong></p>';
    if ($last){echo '<p>Latest attempt: <strong>'.esc($last['version'].' — '.$last['status']).'</strong></p>';if($last['status']!=='verified')echo '<p class="alert">Current installation is unconfirmed after this attempt.</p>';}
    echo '<p class="fine muted">An archive is a backup. Verification confirms controller upload and version checks; physical exhibit acceptance is separate.</p><div class="table-wrap"><table><tr><th>Release</th><th>Archived (UTC)</th><th>Files</th></tr>';
    foreach(q('SELECT id,version,created_at FROM zp_releases WHERE component_id=? ORDER BY id DESC LIMIT 10',[$id]) as $r)echo '<tr><td>'.esc($r['version']).'</td><td>'.esc($r['created_at']).'</td><td><a href="/releases.php?download='.(int)$r['id'].'">Download</a></td></tr>';
    echo '</table></div><div class="table-wrap"><table><tr><th>Attempt (UTC)</th><th>Release</th><th>Result</th></tr>';
    foreach(q('SELECT d.*,r.version FROM zp_deployments d JOIN zp_releases r ON r.id=d.release_id AND r.component_id=d.component_id WHERE d.component_id=? ORDER BY d.started_at DESC LIMIT 10',[$id]) as $d)echo '<tr><td>'.esc($d['started_at']).'</td><td>'.esc($d['version']).'</td><td>'.esc($d['status']).'</td></tr>';
    echo '</table></div><p>Latest 10 archives and attempts. <a href="/releases.php?component='.$id.'">Browse this component’s full release library</a></p></details>';
}
