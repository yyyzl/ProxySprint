"""从同一份 HTML 模板生成各界面入口，避免手工维护造成风格漂移。"""
from pathlib import Path
import json
import html

ROOT = Path(__file__).resolve().parents[1]
SCREENS = [
    ('idle','01-主界面.html','主界面','首次打开，选择网站、地区和节点范围。'),
    ('running','02-测速中.html','测速中','显示请求进度、实时结果和停止操作。'),
    ('done','03-测速结果.html','测速结果','按网站分别推荐，保留失败节点。'),
    ('stopped','04-已取消.html','已取消','停止当前测速，继续显示上次完整报告。'),
    ('empty','05-无匹配节点.html','无匹配节点','范围为空时引导恢复默认筛选条件。'),
    ('error','06-连接失败.html','连接失败','呈现连接错误，并提供重试和设置入口。'),
    ('connection','07-连接设置.html','连接设置','自动发现与手动路径配置。'),
    ('sites','08-网站管理.html','网站管理','查看、编辑、添加和移除测试网站。'),
    ('site-edit','09-添加编辑网站.html','添加 / 编辑网站','名称、HTTP 地址和状态码校验。'),
    ('nodes','10-节点选择.html','节点选择','搜索、批量勾选和预览匹配节点。'),
    ('detail','11-请求详情.html','请求详情','每轮请求的状态码、耗时与失败原因。'),
    ('export','12-导出报告.html','导出报告','CSV / JSON 格式与失败行选择。'),
]

def main():
    source = (ROOT / 'app.html').read_text(encoding='utf-8')
    for state, filename, name, description in SCREENS:
        page = source.replace('data-start="idle"', 'data-start="' + state + '"')
        page = page.replace('<title>ProxySprint · 代理节点测速</title>', '<title>' + name + ' · ProxySprint · 代理节点测速</title>')
        (ROOT / filename).write_text(page, encoding='utf-8')
    cards=[]
    for number,(state, filename, name, description) in enumerate(SCREENS,1):
        cards.append('<a class="screen-card" href="'+html.escape(filename)+'"><div class="screen-image"><img src="assets/screens/'+state+'.png" alt="'+name+'界面预览" loading="lazy"></div><div class="screen-info"><span class="screen-number">'+str(number).zfill(2)+'</span><div><h2>'+name+'</h2><p>'+description+'</p></div><span class="open-arrow" aria-hidden="true">↗</span></div></a>')
    gallery='''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ProxySprint · 代理节点测速 · HTML 原型目录</title>
<link rel="stylesheet" href="assets/prototype.css"><style>
body{padding:clamp(24px,4vw,54px);max-width:1540px;margin:auto}
.gallery-head{display:flex;justify-content:space-between;align-items:center;gap:20px;padding-bottom:26px;border-bottom:1px solid var(--line)}
.gallery-head .brand h1{font-size:28px}.gallery-head p{color:var(--muted);margin-top:8px;font-size:15px}
.open-main{background:#2472c2;color:var(--cream);text-decoration:none;border-radius:7px;padding:12px 20px;white-space:nowrap;font-weight:500}
.prototype-note{font-size:14px;color:var(--muted);line-height:1.8;margin:23px 0 30px;max-width:760px}
.prototype-note strong{color:var(--ink);font-weight:500}
.screens{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:28px 24px}
.screen-card{text-decoration:none;color:inherit;display:block;min-width:0;transition:transform .2s var(--ease)}
.screen-card:hover{transform:translateY(-3px)}.screen-card:hover .screen-image{border-color:#91b7dc}
.screen-image{height:225px;background:var(--sand);border:1px solid var(--line);border-radius:10px;overflow:hidden;display:flex;align-items:center;justify-content:center;transition:border-color .18s}
.screen-image img{width:100%;height:100%;object-fit:contain}
.screen-info{display:flex;align-items:start;gap:12px;padding:15px 1px}.screen-number{font-size:14px;color:var(--blue-ink);line-height:1.6;font-variant-numeric:tabular-nums}
.screen-info h2{font-family:inherit;font-size:16px;margin-bottom:5px;font-weight:600;line-height:1.4}.screen-info p{font-size:13px;color:var(--muted);line-height:1.7}.open-arrow{margin-left:auto;color:var(--muted)}
.gallery-footer{margin-top:32px;border-top:1px solid var(--line);padding-top:22px;color:var(--muted);font-size:13px;display:flex;justify-content:space-between;gap:18px;flex-wrap:wrap}
.gallery-footer a{color:inherit;text-underline-offset:3px}
@media(min-width:1550px){.screen-image{height:250px}}@media(max-width:1080px){.screens{grid-template-columns:repeat(2,minmax(0,1fr))}.screen-image{height:240px}}
@media(max-width:650px){.screens{grid-template-columns:1fr;gap:18px}.screen-image{height:auto;aspect-ratio:1280/860}.gallery-head{align-items:start;flex-wrap:wrap}.gallery-head .brand h1{font-size:23px}.open-main{padding:10px 16px}.prototype-note{margin:20px 0}}
</style></head><body>
<header class="gallery-head"><div><div class="brand"><span class="brand-mark" aria-hidden="true"></span><h1>ProxySprint · 代理节点测速 · 原型目录</h1></div><p>先确认界面与操作，再进入 Flutter 实现。</p></div><a class="open-main" href="01-主界面.html">打开主界面 →</a></header>
<p class="prototype-note"><strong>12 个可操作的 HTML 界面，沿用已确认的设计稿。</strong><br>连接状态、节点与耗时均为模拟数据，用于预览界面和验证交互。名称包含 / 排除收进高级筛选，默认留空。点击下方任一界面即可查看。</p>
<main class="screens">CARDS</main>
<footer class="gallery-footer"><span>双击 HTML 即可打开 · 无需安装开发环境</span><span>设计规范：<a href="https://github.com/esthersjw/esther-design-system" target="_blank" rel="noreferrer">ESTHER不二</a> · CC BY-NC-SA 4.0</span><a href="原型说明.txt">原型范围与验证说明</a></footer>
</body></html>'''
    (ROOT / 'index.html').write_text(gallery.replace('CARDS','\n'.join(cards)),encoding='utf-8')
    (ROOT / 'screens.json').write_text(json.dumps([{'state':a,'file':b,'title':c,'description':d} for a,b,c,d in SCREENS],ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'entry_pages':len(SCREENS),'directory':str(ROOT)},ensure_ascii=True))

if __name__=='__main__':
    main()

