import datetime as dt
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from PIL import Image, ImageDraw
import main as bot


def item(**kw):
    return dict(dict(title='Codex release', body='Verified changes', source='Codex', category='CODEX',
        published=bot.NOW.isoformat(), age_hours=2, score=100,
        url='https://github.com/openai/codex/releases/tag/v1'), **kw)


def edit():
    return dict(index=0, url=item()['url'], headline='한국어 카드뉴스 렌더링 검증',
        summary='개발 도구의 변경 사항을 확인하고 적용 가능성을 검토합니다.',
        changed='원문에 명시된 변경점만 소개하고 확인되지 않은 기능은 제외합니다.',
        why='기존 프로젝트의 호환성을 점검한 뒤 도입 여부를 판단할 수 있습니다.',
        use_case='팀의 샘플 프로젝트에서 변경된 동작을 비교해 보는 방안을 제안합니다.',
        action='원문을 읽고 별도 환경에서 호환성을 검증해 보세요.', importance='높음')


class BotTests(unittest.TestCase):
    def test_recent_and_dedup(self):
        rows = [item(age_hours=40, score=1000), item(title='new', url='https://github.com/openai/codex/releases/tag/v2')]
        self.assertEqual(bot.select_news(rows), [rows[1]])
        self.assertEqual(len(bot.select_news([item(), item(title='different')])), 1)

    def test_release_dates_and_stable_only(self):
        valid = dict(published_at=(bot.NOW-dt.timedelta(hours=1)).isoformat(), body='Changes',
                     html_url=item()['url'], name='v1', tag_name='v1')
        releases = [valid, dict(valid, published_at=(bot.NOW+dt.timedelta(hours=1)).isoformat()),
                    dict(valid, published_at=(bot.NOW-dt.timedelta(hours=73)).isoformat()),
                    dict(valid, prerelease=True), dict(valid, draft=True), dict(valid, body='')]
        with patch.object(bot, 'github', return_value=Mock(status_code=200, json=lambda: releases)):
            self.assertEqual(len(bot.fetch_source(bot.SOURCES[0])), 1)

    @patch.dict(os.environ, {'OPENAI_API_KEY':'test', 'DRY_RUN':'1'})
    def test_no_news_does_not_fabricate(self):
        with patch.object(bot, 'fetch', return_value=[]), patch.object(bot, 'editorial') as editorial, tempfile.TemporaryDirectory() as tmp, patch.object(bot, 'OUT', Path(tmp)):
            bot.main(); editorial.assert_not_called()
            self.assertEqual(json.loads((Path(tmp)/'status.json').read_text())['status'], 'no_news')

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_config_names_only(self):
        with self.assertRaisesRegex(ValueError, 'Missing required configuration: OPENAI_API_KEY'):
            bot.main()

    def test_editorial_mapping_and_limits(self):
        bot.validate_edits([edit()], [item()])
        for changes in [dict(url='https://wrong.example'), dict(index=1), dict(summary='x'*120), dict(importance='critical')]:
            with self.assertRaises(ValueError): bot.validate_edits([dict(edit(), **changes)], [item()])

    @patch.dict(os.environ, {'OPENAI_API_KEY':'test', 'GOOGLE_AI_API_KEY':'test'})
    def test_existing_provider_fallback(self):
        limited = Mock(status_code=429, json=lambda: {'error': {'code':'insufficient_quota'}})
        success = Mock(status_code=200, json=lambda: {'candidates':[{'content':{'parts':[{'text':json.dumps({'cards':[edit()]})}]}}]})
        with patch.object(bot.session, 'post', side_effect=[limited, success]) as post:
            self.assertEqual(bot.editorial([item()]), [edit()])
            self.assertEqual(post.call_count, 2)
            self.assertNotIn('key=', post.call_args.args[0])
        with patch.object(bot.session, 'post', side_effect=[limited, Mock(status_code=403)]):
            with self.assertRaisesRegex(RuntimeError, 'Gemini fallback HTTP 403'):
                bot.editorial([item()])

    def test_model_envelopes_and_product_only_headline(self):
        for envelope in ([edit()], {'cards':[edit()]}):
            self.assertEqual(bot.parse_cards(json.dumps(envelope)), [edit()])
        card = dict(edit(), headline='Codex v1.0')
        self.assertEqual(bot.validate_edits([card], [item()])[0]['headline'], 'Codex v1.0 업데이트')
        with self.assertRaises(ValueError): bot.validate_edits([None], [item()])

    def test_editorial_retry_is_bounded(self):
        with patch.object(bot, 'editorial_once', side_effect=[ValueError('length'), [edit()]]) as call:
            self.assertEqual(bot.editorial([item()]), [edit()])
            self.assertEqual(call.call_count, 2)
        with patch.object(bot, 'editorial_once', side_effect=ValueError('length')) as call:
            with self.assertRaises(ValueError): bot.editorial([item()])
            self.assertEqual(call.call_count, 2)

    def test_blog_excludes_marketing(self):
        self.assertFalse(bot.technical_blog('The next chapter is agentic', 'New analysis shows enterprise adoption'))
        self.assertFalse(bot.technical_blog('Amp puts AI agents to work', 'See how Amp uses models'))
        self.assertTrue(bot.technical_blog('Introducing Codex SDK', 'New API features for developers'))

    def test_wrap_long_tokens(self):
        d = ImageDraw.Draw(Image.new('RGB', (1080, 1350)))
        f = bot.font(35)
        lines = bot.wrap(d, '긴문자열'+'A'*200+'\n두 번째 줄', f, 400, 100)
        self.assertTrue(all(d.textlength(line, font=f) <= 400 for line in lines))
        self.assertGreater(len(lines), 2)

    def test_render_maximum_content(self):
        e = edit()
        for key, limit in bot.FIELDS.items(): e[key] = ('가나다라마바사 아자차카타파하 '*10)[:limit]
        with tempfile.TemporaryDirectory() as tmp, patch.object(bot, 'OUT', Path(tmp)):
            paths = bot.render([item()]*7, [e]*7)
            self.assertEqual(len(paths), 10)
            for p in paths:
                with Image.open(p) as im: self.assertEqual(im.size, (1080, 1350))

    @patch.dict(os.environ, {'OPENAI_API_KEY':'test', 'DRY_RUN':'1'})
    def test_dry_run(self):
        with patch.object(bot, 'fetch', return_value=[item()]), patch.object(bot, 'editorial', return_value=[edit()]), patch.object(bot, 'render', return_value=[]), patch.object(bot, 'send_telegram') as send, tempfile.TemporaryDirectory() as tmp, patch.object(bot, 'OUT', Path(tmp)):
            bot.main(); send.assert_not_called()

    @patch.dict(os.environ, {'OPENAI_API_KEY':'test', 'DRY_RUN':'0', 'TELEGRAM_BOT_TOKEN':'test', 'TELEGRAM_CHAT_ID':'test', 'GITHUB_TOKEN':'test', 'GITHUB_REPOSITORY':'test/test', 'GITHUB_SHA':'test'})
    def test_duplicate_and_uncertain_stop(self):
        with patch.object(bot, 'delivery_exists', return_value=True), patch.object(bot, 'fetch') as fetch:
            bot.main(); fetch.assert_not_called()
        with patch.object(bot, 'delivery_exists', side_effect=[False, True]), patch.object(bot, 'fetch') as fetch:
            with self.assertRaises(RuntimeError): bot.main()
            fetch.assert_not_called()

    @patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN':'sensitive', 'TELEGRAM_CHAT_ID':'test'})
    def test_album_and_uncertain_delivery(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(bot, 'OUT', Path(tmp)):
            paths = [Path(tmp)/f'{i}.jpg' for i in range(4)]
            for p in paths: p.write_bytes(b'image')
            response = Mock(status_code=200, json=lambda: {'ok': True, 'result': [{'message_id':i} for i in range(4)]})
            with patch.object(bot, 'mark_delivery') as mark, patch.object(bot.session, 'post', return_value=response) as post:
                bot.send_telegram(paths, [item()], [edit()])
                self.assertEqual(post.call_count, 1)
                self.assertIn(item()['url'], json.loads(post.call_args.kwargs['data']['media'])[2]['caption'])
                self.assertEqual([c.args[0] for c in mark.call_args_list], ['claimed', 'sent'])
            with patch.object(bot, 'mark_delivery') as mark, patch.object(bot.session, 'post', side_effect=bot.requests.Timeout('sensitive')):
                with self.assertRaisesRegex(RuntimeError, 'uncertain'): bot.send_telegram(paths, [item()], [edit()])
                mark.assert_called_once_with('claimed')

    @patch.dict(os.environ, {'GITHUB_REPOSITORY':'test/test', 'GITHUB_SHA':'test'})
    def test_claim_conflict(self):
        with patch.object(bot, 'github', return_value=Mock(status_code=422)):
            with self.assertRaises(RuntimeError): bot.mark_delivery('claimed')

if __name__ == '__main__': unittest.main()
