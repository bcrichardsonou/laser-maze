<?php
require __DIR__.'/lib.php'; require __DIR__.'/release-lib.php';
transport(); session_boot(); cfg(); $u=require_admin();
// The shared header's logout form posts to this page.
if ($_SERVER['REQUEST_METHOD']==='POST') {
    csrf_check();
    if (($_POST['action'] ?? '')==='logout') {$_SESSION=[];session_destroy();redirect('/?page=login');}
    fail(405,'No release mutations through this page');
}
if (isset($_GET['download'])) {
    $id=filter_var($_GET['download'],FILTER_VALIDATE_INT);
    $r=$id ? one('SELECT * FROM zp_releases WHERE id=?',[$id]) : null;
    if (!$r) fail(404,'Release not found');
    $path=release_path((int)$r['component_id'],$r['sha256']);
    if (!is_file($path) || !hash_equals($r['sha256'],hash_file('sha256',$path))) fail(503,'Archive unavailable or damaged');
    audit((int)$u['id'],'release_download',['release_id'=>(int)$r['id']]);
    header('Content-Type: application/gzip');header('Content-Length: '.filesize($path));
    header('Content-Disposition: attachment; filename="release-'.$r['version'].'.tar.gz"');
    readfile($path);exit;
}
header_page('Software releases',$u);
echo '<h1>Software releases</h1><p>Private release backups and controller-verified deployments. Verification confirms upload and version checks, not full exhibit acceptance.</p>';
$devices=q('SELECT c.*,e.name exhibit FROM zp_components c JOIN zp_exhibits e ON e.id=c.exhibit_id ORDER BY e.name,c.name')->fetchAll();
foreach($devices as $c) {
    $rs=q('SELECT * FROM zp_releases WHERE component_id=? ORDER BY id DESC LIMIT 200',[$c['id']])->fetchAll();
    if (!$rs) continue;
    echo '<section class="panel"><h2>'.esc($c['exhibit'].' / '.$c['name']).'</h2>';
    $latest=one("SELECT d.*,r.version FROM zp_deployments d JOIN zp_releases r ON r.id=d.release_id WHERE d.component_id=? ORDER BY d.started_at DESC,d.updated_at DESC LIMIT 1",[$c['id']]);
    if ($latest) {
        echo '<p>Latest attempt: <strong>'.esc($latest['version'].' — '.$latest['status']).'</strong></p>';
        echo '<p><a href="/releases.php?download='.(int)$latest['release_id'].'">Download files for this attempt</a></p>';
        if ($latest['status']!=='verified') echo '<p>Current installation is unconfirmed after this attempt. Do not assume a previous firmware remains installed.</p>';
    }
    echo '<table><thead><tr><th>Release</th><th>Archived (UTC)</th><th>Notes</th><th>Files</th></tr></thead><tbody>';
    foreach($rs as $r) {$m=json_decode($r['manifest'],true);echo '<tr><td>'.esc($r['version']).'</td><td>'.esc($r['created_at']).'</td><td>'.esc($m['notes'] ?? '').'</td><td><a href="/releases.php?download='.(int)$r['id'].'">Download archive</a><br><small>SHA-256 '.esc($r['sha256']).'</small></td></tr>';}
    echo '</tbody></table><h3>Deployment history</h3><table><thead><tr><th>Release</th><th>Started (UTC)</th><th>Result</th><th>Verified versions</th></tr></thead><tbody>';
    $ds=q('SELECT d.*,r.version FROM zp_deployments d JOIN zp_releases r ON r.id=d.release_id WHERE d.component_id=? ORDER BY d.started_at DESC LIMIT 100',[$c['id']])->fetchAll();
    foreach($ds as $d) echo '<tr><td>'.esc($d['version']).'</td><td>'.esc($d['started_at']).'</td><td>'.esc($d['status']).'<br>'.esc($d['reason'] ?? '').'</td><td>'.esc($d['firmware_version'] ?? 'Unconfirmed').'<br>'.esc($d['python_version'] ?? 'Unconfirmed').'</td></tr>';
    echo '</tbody></table></section>';
}
if (!one('SELECT id FROM zp_releases LIMIT 1')) echo '<p>No releases archived yet.</p>';
footer_page();
