<?php
/** Hostinger CLI cron -> existing main posting workflow. No WordPress/model credentials. */
declare(strict_types=1);

const TP_REPO = 'hhj4861/wp-auto-blog';
const TP_WORKFLOW = 'auto-post.yml';
const TP_COOLDOWN = 900;
const TP_MAX_ATTEMPTS = 3;

function tp_target(DateTimeImmutable $now): ?string {
    $local = $now->setTimezone(new DateTimeZone('Asia/Seoul'));
    $hour = (int)$local->format('G');
    return $hour < 9 ? null : $local->format('Y-m-d').':'.($hour < 18 ? 'morning' : 'evening');
}

function tp_stamp(string $value): DateTimeImmutable {
    if (!preg_match('/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-](?:0\d|1[0-4]):[0-5]\d)$/D', $value)) throw new RuntimeException('invalid_timestamp');
    $stamp = new DateTimeImmutable($value);
    $errors = DateTimeImmutable::getLastErrors();
    if ($errors !== false && ($errors['warning_count'] || $errors['error_count'])) throw new RuntimeException('invalid_timestamp');
    return $stamp;
}

function tp_ledger(string $body): array {
    $shape = json_decode($body, false, 512, JSON_THROW_ON_ERROR);
    if (!$shape instanceof stdClass || !($shape->runs ?? null) instanceof stdClass) throw new RuntimeException('invalid_remote_state');
    $data = json_decode($body, true, 512, JSON_THROW_ON_ERROR);
    if (!is_array($data) || !in_array($data['schema_version'] ?? null, [1,2], true)
        || !is_array($data['runs'] ?? null)) throw new RuntimeException('invalid_remote_state');
    $result = [];
    foreach ($data['runs'] as $key => $row) {
        $key = (string)$key;
        if ($data['schema_version'] === 1) $key .= ':morning';
        if (!preg_match('/^(\d{4}-\d{2}-\d{2}):(morning|evening)$/D', $key, $m)
            || !is_array($row) || !preg_match('/^[1-9][0-9]*$/D', (string)($row['run_id'] ?? ''))
            || !in_array($row['status'] ?? null, ['started','success','failure','cancelled'], true)
            || !in_array($row['category'] ?? null, ['생활정보','취업','건강','생산성','리뷰','테크'], true)
            || ($data['schema_version'] === 2 && ($row['slot'] ?? null) !== $m[2])
            || !is_string($row['claimed_at'] ?? null)) throw new RuntimeException('invalid_remote_state');
        if ((new DateTimeImmutable($m[1]))->format('Y-m-d') !== $m[1]) throw new RuntimeException('invalid_remote_state');
        tp_stamp($row['claimed_at']);
        $result[$key] = $row;
    }
    return $result;
}

function tp_local(string $path): array {
    if (is_link($path)) throw new RuntimeException('invalid_local_state');
    if (!file_exists($path)) return ['version'=>1, 'slots'=>[]];
    $data = json_decode((string)file_get_contents($path), true, 512, JSON_THROW_ON_ERROR);
    if (!is_array($data) || ($data['version'] ?? null) !== 1 || !is_array($data['slots'] ?? null)) {
        throw new RuntimeException('invalid_local_state');
    }
    foreach ($data['slots'] as $key => $row) {
        if (!preg_match('/^(\d{4}-\d{2}-\d{2}):(morning|evening)$/D', (string)$key, $m)
            || !is_array($row) || !is_int($row['attempts'] ?? null)
            || $row['attempts'] < 0 || $row['attempts'] > TP_MAX_ATTEMPTS
            || !in_array($row['status'] ?? null, ['pending','accepted','unknown','claimed'], true)
            || !is_string($row['last_attempt'] ?? null)) throw new RuntimeException('invalid_local_state');
        if ((new DateTimeImmutable($m[1]))->format('Y-m-d') !== $m[1]) throw new RuntimeException('invalid_local_state');
        tp_stamp($row['last_attempt']);
    }
    return $data;
}

function tp_save(string $path, array $data): void {
    $tmp = $path.'.'.bin2hex(random_bytes(8)).'.tmp';
    $body = json_encode($data, JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE)."\n";
    if (file_put_contents($tmp, $body, LOCK_EX) !== strlen($body)) throw new RuntimeException('state_write_failed');
    if (!chmod($tmp, 0600)) throw new RuntimeException('state_write_failed');
    if (!rename($tmp, $path)) throw new RuntimeException('state_write_failed');
}

function tp_payload(string $target): array {
    return ['ref'=>'main', 'inputs'=>['mode'=>'queue', 'writer_provider'=>'codex',
        'publish'=>true, 'scheduled_recovery'=>true, 'scheduled_target'=>$target]];
}

function tp_tick(DateTimeImmutable $now, string $dir, callable $api, bool $apply): array {
    $target = tp_target($now);
    if ($target === null) return ['status'=>'before_first_slot'];
    $path = $dir.'/timer-state.json';
    $local = tp_local($path);
    $row = $local['slots'][$target] ?? null;
    if (($row['status'] ?? '') === 'claimed') return ['status'=>'already_claimed','target'=>$target];
    $kst = $now->setTimezone(new DateTimeZone('Asia/Seoul'));
    $start = str_ends_with($target, ':morning') ? 9 : 18;
    if (((int)$kst->format('G') !== $start || (int)$kst->format('i') >= 30)
        && (int)$kst->format('i') % 5 !== 0) return ['status'=>'waiting_for_check','target'=>$target];
    $ledger = tp_ledger($api('GET','contents/data/scheduled_post_runs.json?ref=main',null));
    $cutoff = $kst->modify('-14 days')->format('Y-m-d');
    $local['slots'] = array_filter($local['slots'], fn($k) => substr($k,0,10) >= $cutoff, ARRAY_FILTER_USE_KEY);
    if (isset($ledger[$target])) {
        if ($apply) {
            $local['slots'][$target] = ['attempts'=>$row['attempts'] ?? 0,
                'last_attempt'=>$now->format(DATE_ATOM),'status'=>'claimed'];
            tp_save($path,$local);
        }
        return ['status'=>'already_attempted','target'=>$target,'outcome'=>$ledger[$target]['status']];
    }
    if ($row !== null) {
        if ($now->getTimestamp() - tp_stamp($row['last_attempt'])->getTimestamp() < TP_COOLDOWN) {
            return ['status'=>'awaiting_claim','target'=>$target];
        }
        if ($row['attempts'] >= TP_MAX_ATTEMPTS) return ['status'=>'unconfirmed_dispatch_limit','target'=>$target];
    }
    if (!$apply) return ['status'=>'would_dispatch','target'=>$target];
    $local['slots'][$target] = ['attempts'=>($row['attempts'] ?? 0)+1,
        'last_attempt'=>$now->format(DATE_ATOM),'status'=>'pending'];
    tp_save($path,$local); // Durable BEFORE POST; ambiguity is never an immediate retry.
    try {
        $api('POST','actions/workflows/'.TP_WORKFLOW.'/dispatches',tp_payload($target));
        $status = 'dispatch_accepted'; $local['slots'][$target]['status'] = 'accepted';
    } catch (Throwable $e) {
        $status = 'dispatch_unconfirmed'; $local['slots'][$target]['status'] = 'unknown';
        $reason = preg_match('/^github_http_\d{1,3}$/D', $e->getMessage()) ? $e->getMessage() : 'request_failed_or_response_unknown';
    }
    tp_save($path,$local);
    return ['status'=>$status,'target'=>$target] + (isset($reason) ? ['reason'=>$reason] : []);
}

function tp_token(string $dir): string {
    $path = $dir.'/github-token.txt';
    if (!is_file($path) || is_link($path) || (fileperms($path) & 0077) !== 0) {
        throw new RuntimeException('private_token_file_required');
    }
    $token = trim((string)file_get_contents($path));
    if (!preg_match('/^github_pat_[A-Za-z0-9_]{20,250}$/D',$token)) throw new RuntimeException('scoped_token_required');
    return $token;
}

function tp_http(string $dir, string $method, string $path, ?array $payload): string {
    $allowed = ['GET'=>'contents/data/scheduled_post_runs.json?ref=main', 'POST'=>'actions/workflows/'.TP_WORKFLOW.'/dispatches'];
    if (($allowed[$method] ?? null) !== $path) throw new RuntimeException('invalid_request');
    $headers = ['User-Agent: TrendPulse-Hosting-Timer','X-GitHub-Api-Version: 2022-11-28',
        'Accept: '.($method === 'GET' ? 'application/vnd.github.raw+json' : 'application/vnd.github+json')];
    if ($method === 'POST') $headers[] = 'Authorization: Bearer '.tp_token($dir);
    $curl = curl_init('https://api.github.com/repos/'.TP_REPO.'/'.$path);
    $body = '';
    curl_setopt_array($curl, [CURLOPT_HTTPHEADER=>$headers,CURLOPT_FOLLOWLOCATION=>false,
        CURLOPT_SSL_VERIFYPEER=>true,CURLOPT_SSL_VERIFYHOST=>2,CURLOPT_PROTOCOLS=>CURLPROTO_HTTPS,
        CURLOPT_CONNECTTIMEOUT=>10,CURLOPT_TIMEOUT=>45,
        CURLOPT_WRITEFUNCTION=>function($ch,$chunk) use (&$body) {
            if (strlen($body)+strlen($chunk)>2097152) return 0;
            $body.=$chunk; return strlen($chunk);
        }]);
    if ($method === 'POST') {
        $headers[] = 'Content-Type: application/json';
        curl_setopt_array($curl,[CURLOPT_HTTPHEADER=>$headers,CURLOPT_POST=>true,
            CURLOPT_POSTFIELDS=>json_encode($payload,JSON_THROW_ON_ERROR)]);
    }
    $ok = curl_exec($curl); $code = (int)curl_getinfo($curl,CURLINFO_HTTP_CODE); curl_close($curl);
    if ($ok === false || ($method === 'GET' ? $code !== 200 : !in_array($code,[200,204],true))) {
        throw new RuntimeException('github_http_'.$code); // No response/header/token logging.
    }
    return $body;
}

function tp_main(array $args): int {
    if (PHP_SAPI !== 'cli') { http_response_code(404); return 1; }
    $result = [];
    try {
        if (count($args)>1 || (count($args)===1 && !in_array($args[0],['--apply','--probe'],true))) {
            throw new RuntimeException('invalid_arguments');
        }
        if (preg_match('~/(public_html|www|htdocs)(/|$)~',__DIR__)) throw new RuntimeException('private_directory_required');
        if (!extension_loaded('curl')) throw new RuntimeException('curl_required');
        $now = new DateTimeImmutable('now',new DateTimeZone('UTC'));
        $api = fn($method,$path,$payload) => tp_http(__DIR__,$method,$path,$payload);
        $apply = ($args[0] ?? '') === '--apply';
        if (($args[0] ?? '') === '--probe') {
            $ledger = tp_ledger($api('GET','contents/data/scheduled_post_runs.json?ref=main',null));
            $target = tp_target($now);
            $result = ['status'=>'probe_ok','php_version'=>PHP_VERSION,'target'=>$target,
                'remote_outcome'=>$ledger[$target]['status'] ?? null,'token_file_present'=>is_file(__DIR__.'/github-token.txt')];
        } elseif ($apply) {
            tp_token(__DIR__); // Missing/invalid configuration must not look healthy on a claimed day.
            umask(0077);
            if (is_link(__DIR__.'/timer.lock')) throw new RuntimeException('lock_failed');
            $lock = fopen(__DIR__.'/timer.lock','c');
            if ($lock === false) throw new RuntimeException('lock_failed');
            chmod(__DIR__.'/timer.lock',0600);
            if (!flock($lock,LOCK_EX|LOCK_NB)) $result = ['status'=>'another_timer_running'];
            else {
                try { $result = tp_tick($now,__DIR__,$api,true); }
                finally { flock($lock,LOCK_UN); }
            }
            fclose($lock);
        } else $result = tp_tick($now,__DIR__,$api,false);
    } catch (Throwable $e) {
        // Only fixed local identifiers may reach hosting logs, never arbitrary exception text.
        $known = ['invalid_arguments','private_directory_required','curl_required','private_token_file_required',
            'scoped_token_required','invalid_remote_state','invalid_local_state','invalid_timestamp','state_write_failed','lock_failed'];
        $code = $e->getMessage();
        $result = ['status'=>'timer_failed','reason'=>in_array($code,$known,true) || preg_match('/^github_http_\d{1,3}$/D',$code) ? $code : 'invalid_data_or_runtime'];
    }
    $result['checked_at'] = gmdate('c');
    echo json_encode($result,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES)."\n";
    return in_array($result['status'],['timer_failed','dispatch_unconfirmed','unconfirmed_dispatch_limit'],true) ? 1 : 0;
}

if (isset($_SERVER['SCRIPT_FILENAME']) && realpath($_SERVER['SCRIPT_FILENAME']) === __FILE__) {
    exit(tp_main(array_slice($argv ?? [],1)));
}
