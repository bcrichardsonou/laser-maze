<?php
require __DIR__.'/lib.php';
transport(); session_boot(); cfg();
$page=is_string($_GET['page'] ?? null) ? $_GET['page'] : 'overview';
$notice=''; $generated='';
if ($_SERVER['REQUEST_METHOD']==='POST') {
    csrf_check(); $action=text_input('action',40);
    if ($action==='logout') { $_SESSION=[]; session_destroy(); redirect('/?page=login'); }
    elseif ($action==='login') {
        ip_limit('login'); $email=strtolower(text_input('email',254)); limit('login:account:'.$email,10,900);
        $password=text_input('password',72); $u=one('SELECT * FROM zp_users WHERE email=?',[$email]);
        $dummy='$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2uheWG/igi.';
        $match=password_verify($password,$u['password_hash'] ?? $dummy);
        if (!$u || !$u['active'] || !$u['password_hash'] || !$match) { $notice='Email or password not accepted.'; $page='login'; }
        else { session_regenerate_id(true); $_SESSION['pending']=['id'=>(int)$u['id'],'version'=>(int)$u['session_version'],'at'=>time()]; unset($_SESSION['enroll_secret']); redirect('/?page='.($u['totp_secret']?'mfa':'enroll')); }
    }
    elseif ($action==='mfa' || $action==='enroll') {
        $u=pending_user(); ip_limit('mfa',30); limit('mfa:user:'.$u['id'],10,900); $code=text_input('code',6);
        if ($action==='enroll' && !$u['totp_secret'] && isset($_SESSION['enroll_secret'])) {
            $raw=base64_decode($_SESSION['enroll_secret'],true); $step=totp_step($raw,$code);
            if ($step!==null) { $s=q('UPDATE zp_users SET totp_secret=?,totp_last_step=? WHERE id=? AND totp_secret IS NULL AND active=1 AND session_version=?',[seal($raw),$step,$u['id'],$u['session_version']]); if ($s->rowCount()) sign_in($u); }
        } elseif ($action==='mfa' && $u['totp_secret']) {
            $step=totp_step(unseal($u['totp_secret']),$code);
            if ($step!==null) { $s=q('UPDATE zp_users SET totp_last_step=? WHERE id=? AND totp_last_step<? AND active=1 AND session_version=?',[$step,$u['id'],$step,$u['session_version']]); if ($s->rowCount()) sign_in($u); }
        }
        $notice='Code not accepted. Wait for a new code and try again.'; $page=$action;
    }
    elseif ($action==='setup') {
        ip_limit('setup',10);
        if (one("SELECT id FROM zp_users WHERE role='admin'") || one("SELECT value FROM zp_settings WHERE name='setup_complete'")) fail(403,'Setup already completed.');
        $key=text_input('setup_key',200); $configured=cfg()['setup_key'] ?? '';
        if (strlen($configured)<48 || str_starts_with($configured,'REPLACE_') || !hash_equals($configured,$key)) fail(403,'Setup key not accepted.');
        $name=text_input('name'); $email=strtolower(text_input('email',254)); $password=text_input('password',72);
        if (!filter_var($email,FILTER_VALIDATE_EMAIL) || strlen($password)<14) fail(400,'Use a valid email and a password of 14–72 characters.');
        db()->beginTransaction();
        q("INSERT INTO zp_settings(name,value) VALUES ('setup_complete','1')");
        q("INSERT INTO zp_users(name,email,password_hash,role) VALUES (?,?,?,'admin')",[$name,$email,password_hash($password,PASSWORD_DEFAULT)]);
        $uid=(int)db()->lastInsertId(); audit($uid,'setup_complete'); db()->commit(); redirect('/?page=login');
    }
    elseif ($action==='forgot') {
        ip_limit('forgot',5); $email=strtolower(text_input('email',254)); limit('recovery:'.$email,3,3600);
        $u=one('SELECT * FROM zp_users WHERE email=? AND active=1',[$email]);
        if ($u && cfg()['mail_enabled']) { send_link($u['email'],issue_link((int)$u['id'])); }
        $notice='If recovery email is configured and the account is eligible, a link has been sent. Otherwise contact the administrator.'; $page='forgot';
    }
    elseif ($action==='password') {
        ip_limit('password',10); $token=text_input('token',64); $pw=text_input('password',72);
        if (strlen($pw)<14) fail(400,'Use a password of 14–72 characters.');
        db()->beginTransaction();
        $t=one('SELECT t.*,u.active FROM zp_tokens t JOIN zp_users u ON u.id=t.user_id WHERE token_hash=? AND expires_at>UTC_TIMESTAMP() FOR UPDATE',[hash('sha256',$token)]);
        if (!$t || !$t['active']) { db()->rollBack(); fail(400,'Link expired or already used.'); }
        q('UPDATE zp_users SET password_hash=?,session_version=session_version+1 WHERE id=?',[password_hash($pw,PASSWORD_DEFAULT),$t['user_id']]);
        q('DELETE FROM zp_tokens WHERE user_id=?',[$t['user_id']]); audit((int)$t['user_id'],'password_set'); db()->commit(); redirect('/?page=login');
    }
    else {
        $u=require_admin();
        if ($action==='museum') { q('INSERT INTO zp_museums(name) VALUES (?)',[text_input('name')]); }
        elseif ($action==='location') {
            $mid=id_input('museum_id'); if (!one('SELECT id FROM zp_museums WHERE id=?',[$mid])) fail(400,'Unknown museum');
            $tz=text_input('timezone',80); if (!in_array($tz,DateTimeZone::listIdentifiers(),true)) fail(400,'Use a valid timezone identifier, such as America/Chicago.');
            q('INSERT INTO zp_locations(museum_id,name,timezone) VALUES (?,?,?)',[$mid,text_input('name'),$tz]);
        }
        elseif ($action==='exhibit') {
            $lid=id_input('location_id'); location_row($lid);$name=text_input('name');
            db()->beginTransaction();
            try {q('INSERT INTO zp_exhibits(location_id,name) VALUES (?,?)',[$lid,$name]);$eid=(int)db()->lastInsertId();
                $generated=exhibit_share_create($eid,null,$name);db()->commit();
            } catch(Throwable $error){db()->rollBack();throw $error;}
        }
        elseif ($action==='move') {
            $eid=id_input('exhibit_id'); $lid=id_input('location_id'); location_row($lid);
            if (!one('SELECT id FROM zp_exhibits WHERE id=?',[$eid])) fail(400,'Unknown exhibit');
            // An old location link must not follow an exhibit into a new client/location.
            db()->beginTransaction(); q('UPDATE zp_exhibits SET location_id=? WHERE id=?',[$lid,$eid]);
            q('UPDATE zp_shares SET active=0 WHERE exhibit_id=?',[$eid]);
            q('DELETE FROM zp_permissions WHERE exhibit_id=?',[$eid]); q('UPDATE zp_exhibits SET point_user_id=NULL WHERE id=?',[$eid]);
            audit((int)$u['id'],'exhibit_moved_access_cleared',['exhibit_id'=>$eid,'location_id'=>$lid]); db()->commit();
        }
        elseif ($action==='remote-access') {
            $cid=id_input('component_id');
            if (!one('SELECT id FROM zp_components WHERE id=? AND active=1',[$cid])) fail(400,'Choose an active reporting component.');
            try {$reference=remote_access_validate($_POST);}catch (InvalidArgumentException $e){fail(400,$e->getMessage());}
            $setting='remote_access:'.$cid;
            if (!array_filter($reference,fn($value)=>$value!=='')) q('DELETE FROM zp_settings WHERE name=?',[$setting]);
            else q('INSERT INTO zp_settings(name,value) VALUES (?,?) ON DUPLICATE KEY UPDATE value=VALUES(value)',[$setting,json_encode($reference,JSON_THROW_ON_ERROR)]);
        }
        elseif ($action==='component') {
            $eid=id_input('exhibit_id'); if (!one('SELECT id FROM zp_exhibits WHERE id=? AND active=1',[$eid])) fail(400,'Unknown exhibit');
            $key=bin2hex(random_bytes(32)); $device='zoco-'.bin2hex(random_bytes(8));
            q('INSERT INTO zp_components(exhibit_id,name,device_id,key_hash) VALUES (?,?,?,?)',[$eid,text_input('name'),$device,hash('sha256',$key)]);
            $generated=json_encode(['url'=>rtrim(cfg()['base_url'],'/').'/ingest.php','device_id'=>$device,'upload_key'=>$key,'local_db'=>'~/zoco-logs/events.sqlite3','software_version'=>'simulator-v1'],JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES);
            audit((int)$u['id'],'component_registered',['exhibit_id'=>$eid,'device_id'=>$device]);
            $_SESSION['device_config']=$generated; redirect('/?page=device-config');
        }
        elseif ($action==='retire') { $cid=id_input('component_id'); q('UPDATE zp_components SET active=0 WHERE id=?',[$cid]); }
        elseif ($action==='replace') {
            $old=id_input('old_id'); $new=id_input('new_id'); $a=one('SELECT * FROM zp_components WHERE id=?',[$old]); $b=one('SELECT * FROM zp_components WHERE id=?',[$new]);
            if (!$a || !$b || $old===$new || !$b['active'] || $a['exhibit_id']!==$b['exhibit_id']) fail(400,'Choose different components belonging to the same exhibit.');
            q('UPDATE zp_components SET active=0,replaced_by=? WHERE id=?',[$new,$old]);
        }
        elseif ($action==='invite') {
            $email=strtolower(text_input('email',254)); if (!filter_var($email,FILTER_VALIDATE_EMAIL)) fail(400,'Invalid email');
            if (one('SELECT id FROM zp_users WHERE email=?',[$email])) fail(400,'That email already has an account. Use a new access link for the existing account.');
            q('INSERT INTO zp_users(name,email) VALUES (?,?)',[text_input('name'),$email]);
            $id=(int)db()->lastInsertId(); $generated=issue_link($id); send_link($email,$generated);
        }
        elseif ($action==='access-link') {
            $id=id_input('user_id'); $target=one("SELECT * FROM zp_users WHERE id=? AND active=1 AND role='staff'",[$id]); if (!$target) fail(400,'Unknown active staff account');
            $generated=issue_link($id); send_link($target['email'],$generated);
        }
        elseif ($action==='user-active') {
            $id=id_input('user_id'); q("UPDATE zp_users SET active=1-active,session_version=session_version+1 WHERE id=? AND role='staff'",[$id]); q('DELETE FROM zp_tokens WHERE user_id=?',[$id]);
        }
        elseif ($action==='permission') {
            $id=id_input('user_id'); $eid=id_input('exhibit_id');
            if (!one("SELECT id FROM zp_users WHERE id=? AND role='staff'",[$id]) || !one('SELECT id FROM zp_exhibits WHERE id=?',[$eid])) fail(400,'Unknown staff or exhibit');
            if (isset($_POST['remove'])) {q('DELETE FROM zp_permissions WHERE user_id=? AND exhibit_id=?',[$id,$eid]); q('UPDATE zp_exhibits SET point_user_id=NULL WHERE id=? AND point_user_id=?',[$eid,$id]);}
            else {
                $control=isset($_POST['control'])?1:0; $manage=isset($_POST['manage'])?1:0; $detail=(isset($_POST['detail']) || $control || $manage)?1:0;
                q('INSERT INTO zp_permissions(user_id,exhibit_id,detail,control,manage) VALUES (?,?,?,?,?) ON DUPLICATE KEY UPDATE detail=VALUES(detail),control=VALUES(control),manage=VALUES(manage)',[$id,$eid,$detail,$control,$manage]);
                if (isset($_POST['point'])) q('UPDATE zp_exhibits SET point_user_id=? WHERE id=?',[$id,$eid]);
            }
            // Existing browser sessions must reload permissions immediately on their next request.
        }
        elseif ($action==='share') {
            $scope=text_input('scope',20); $id=id_input('scope_id'); $eid=null;$lid=null;
            if ($scope==='exhibit' && one('SELECT id FROM zp_exhibits WHERE id=?',[$id])) $eid=$id;
            elseif ($scope==='location' && one('SELECT id FROM zp_locations WHERE id=?',[$id])) $lid=$id;
            else fail(400,'Invalid sharing scope');
            db()->beginTransaction();try {$generated=exhibit_share_create($eid,$lid,text_input('label'));db()->commit();}catch(Throwable $error){db()->rollBack();throw $error;}
        }
        elseif ($action==='revoke-share') { q('UPDATE zp_shares SET active=0 WHERE id=?',[id_input('share_id')]); }
        else fail(400,'Unknown action');
        $detail=[]; foreach (['exhibit_id','component_id','user_id','share_id','old_id','new_id'] as $field) if (isset($_POST[$field])) $detail[$field]=(int)$_POST[$field];
        audit((int)$u['id'],$action,$detail); $notice='Saved.'; $page='admin';
    }
}

// Public account flows. No exhibit data is emitted before full authentication.
if (in_array($page,['login','setup','forgot','password','mfa','enroll'],true)) {
    header_page('Account access'); echo '<section class="panel narrow">'; if ($notice) echo '<p class="alert">'.esc($notice).'</p>';
    if ($page==='login') {
        echo '<h1>Welcome back</h1><p class="muted">One sign-in for your assigned exhibits.</p><form method="post">'.csrf_field().'<input type="hidden" name="action" value="login"><label>Email<input type="email" name="email" autocomplete="username" required></label><label>Password<input type="password" name="password" autocomplete="current-password" maxlength="72" required></label><button>Sign in</button></form><p><a href="/?page=forgot">Forgot your password?</a></p>';
    } elseif ($page==='setup') {
        if (one("SELECT value FROM zp_settings WHERE name='setup_complete'")) fail(403,'Setup already completed.');
        echo '<h1>Create your administrator account</h1><form method="post">'.csrf_field().'<input type="hidden" name="action" value="setup"><label>Private setup key<input type="password" name="setup_key" required></label><label>Your name<input name="name" required></label><label>Email<input type="email" name="email" required></label><label>Password (14–72 characters)<input type="password" name="password" minlength="14" maxlength="72" autocomplete="new-password" required></label><button>Create account</button></form>';
    } elseif ($page==='forgot') {
        echo '<h1>Password recovery</h1><form method="post">'.csrf_field().'<input type="hidden" name="action" value="forgot"><label>Email<input type="email" name="email" required></label><button>Request access link</button></form><p><a href="/?page=login">Back to sign in</a></p>';
    } elseif ($page==='password') {
        $token=$_GET['token'] ?? ''; if (!is_string($token) || !preg_match('/^[a-f0-9]{64}$/D',$token)) fail(400,'Invalid access link');
        echo '<h1>Set your password</h1><form method="post">'.csrf_field().'<input type="hidden" name="action" value="password"><input type="hidden" name="token" value="'.esc($token).'"><label>New password (14–72 characters)<input type="password" name="password" minlength="14" maxlength="72" autocomplete="new-password" required></label><button>Save password</button></form><p>Your authenticator remains required if it is already enrolled.</p>';
    } else {
        $u=pending_user();
        if ($page==='enroll' && !$u['totp_secret']) {
            if (!isset($_SESSION['enroll_secret'])) $_SESSION['enroll_secret']=base64_encode(random_bytes(20));
            $secret=base32(base64_decode($_SESSION['enroll_secret'],true));
            echo '<h1>Set up two-factor sign-in</h1><p>In your authenticator app, add a time-based account named ZoCo and enter this setup key. No paid service is needed.</p><pre>'.esc($secret).'</pre><p>Keep access to your authenticator. Self-service recovery codes are not included in this first release.</p>';
        } elseif ($u['totp_secret']) { $page='mfa'; echo '<h1>Verify your sign-in</h1>'; }
        else redirect('/?page=enroll');
        echo '<form method="post">'.csrf_field().'<input type="hidden" name="action" value="'.esc($page).'"><label>Six-digit authenticator code<input name="code" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" autocomplete="one-time-code" required></label><button>Continue</button></form>';
    }
    echo '</section>'; footer_page(); exit;
}
$u=require_user();
if ($page==='device-config') {
    require_admin(); $content=$_SESSION['device_config'] ?? null; unset($_SESSION['device_config']);
    header_page('Component setup',$u); echo '<section class="panel"><h1>Save the component configuration</h1><p>This credential is shown once. Save the text as <strong>device-config.json</strong> beside the agent on your laptop or Pi. Keep it private.</p>';
    if ($content) echo '<pre>'.esc($content).'</pre>'; else echo '<p>Configuration already displayed. If it was lost, retire this component and register a replacement.</p>';
    echo '<a href="/?page=admin">Back to management</a></section>'; footer_page(); exit;
}
if ($page==='admin') { require_admin(); require __DIR__.'/views/admin.php'; exit; }
if ($page==='exhibit' || $page==='export') {
    $eid=filter_var($_GET['id'] ?? '',FILTER_VALIDATE_INT); if (!$eid || !allowed($u,$eid)) fail(403,'Exhibit access required.');
    $e=one('SELECT e.*,l.name location_name,l.timezone,m.name museum_name FROM zp_exhibits e JOIN zp_locations l ON l.id=e.location_id JOIN zp_museums m ON m.id=l.museum_id WHERE e.id=?',[$eid]); if (!$e) fail(404,'Exhibit not found');
    if ($page==='export') {
        if (!allowed($u,$eid,'detail')) fail(403,'Detailed log access required.');
        header('Content-Type: text/csv; charset=utf-8'); header('Content-Disposition: attachment; filename="zoco-exhibit-'.$eid.'-logs.csv"');
        $f=fopen('php://output','w'); fputcsv($f,['component','device_id','occurred_at_utc','kind','payload'],',','"','');
        $s=q('SELECT c.name,c.device_id,v.occurred_at,v.kind,v.payload FROM zp_events v JOIN zp_components c ON c.id=v.component_id WHERE c.exhibit_id=? ORDER BY v.occurred_at DESC LIMIT 20000',[$eid]);
        while ($r=$s->fetch(PDO::FETCH_NUM)) { foreach ($r as &$v) if (preg_match('/^[=+@\-\t\r\n]/',(string)$v)) $v="'".$v; unset($v); fputcsv($f,$r,',','"',''); } fclose($f); exit;
    }
    header_page($e['name'],$u); render_exhibit($e,allowed($u,$eid,'detail'),false,$u); footer_page(); exit;
}
header_page('Overview',$u); require __DIR__.'/views/overview.php'; footer_page();
