"""Create a clean, local workspace without contacting external services."""
import argparse
from datetime import date
import json
from pathlib import Path
import shutil

SKILL = Path(__file__).resolve().parents[1]


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def initialize(workspace, batch_date, target=100):
    date.fromisoformat(batch_date)
    if target < 1:
        raise ValueError('target must be positive')
    workspace = Path(workspace).expanduser().resolve()
    if workspace == SKILL or SKILL in workspace.parents:
        raise ValueError('Use a separate workspace outside the installed skill')
    project = workspace / ('candidate_research_' + batch_date)
    if project.exists():
        raise FileExistsError('Batch already exists; use workflow.py status: ' + str(project))
    workspace.mkdir(parents=True, exist_ok=True)
    project.mkdir()
    for folder in ['profiles', 'screenshots', 'post_audits', 'native_media', 'official_links']:
        (project / folder).mkdir()
    for name in ['production_reviews', 'screening', 'scores', 'identity_aliases']:
        write(project / (name + '.json'), {})
    write(project / 'contact_email_aliases.json', [])
    write(project / 'existing.json', [])
    write(project / 'excluded_handles.json', [])
    write(project / 'historical_exclusions.json', {'handles': [], 'emails': [], 'person_keys': []})
    shutil.copyfile(SKILL / 'assets/schema.json', project / 'schema.json')
    write(project / 'project.json', {
        'date': batch_date, 'target': target, 'cdp': 'http://127.0.0.1:9222',
        'ffmpeg_bin': '', 'history_projects': [], 'excluded_handles': [],
        'min_followers': 1000, 'max_followers': 100000, 'require_public_email': True,
        'content_score_threshold': 27, 'discovery_region_filter': False,
        'allow_reviewed_image_deletion': False,
        'output_name': f'NUWARIA_新候选达人{target}_{batch_date}.xlsx',
        'notion_env': str(workspace / '.env'), 'notion_data_source': '', 'notion_sop': '',
        'notion_main_page': '', 'notion_tracking_data_source': '',
        'notion_stats_table': '', 'notion_stats_paragraph': '',
        'zoho_auth': str(workspace / 'zoho_mail.auth.json'), 'sender_email': '',
        'user_logistics_hold_regions': [],
        'user_logistics_note': '首次配置：与团队确认当前可寄送地区后再联系。',
        'history_scope_note': '空白初始化；尚未读取团队 Notion 或本地历史。'
    })
    (project / 'AGENTS.md').write_text(
        '使用已安装的 nuwaria-creator-research 技能。审核主表 production_reviews.json。'
        '先核实团队历史去重范围；空白初始状态不是全团队查重完成。'
        '外发和 Notion 写入依照当前用户授权，安装技能不构成授权。\n', encoding='utf-8')
    for name, content in {
        '.env.example': 'NOTION_TOKEN=\n',
        '.gitignore': '*\n!.gitignore\n',
    }.items():
        path = workspace / name
        if not path.exists():
            path.write_text(content, encoding='utf-8')
    auth = workspace / 'zoho_mail.auth.example.json'
    if not auth.exists():
        write(auth, {k: '' for k in ['accounts_url', 'mail_base_url', 'account_id',
                                     'client_id', 'client_secret', 'refresh_token', 'from_email']})
    return project


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--date', required=True)
    parser.add_argument('--target', type=int, default=100)
    args = parser.parse_args()
    print(initialize(args.workspace, args.date, args.target))
