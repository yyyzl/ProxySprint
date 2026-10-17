/* 本文件仅模拟交互。所有节点、计时和连接状态均为原型数据。 */
document.addEventListener('alpine:init', function () {
  Alpine.data('probeUI', function () {
    const nodeList = [
      {id:'jp1',name:'日本 · 东京 01',region:'jp',provider:'主订阅'},
      {id:'jp2',name:'日本 · 大阪 02',region:'jp',provider:'备用订阅'},
      {id:'sg1',name:'新加坡 · 狮城 01',region:'sg',provider:'主订阅'},
      {id:'sg2',name:'新加坡 · 狮城 02',region:'sg',provider:'备用订阅'},
      {id:'hk1',name:'香港 · 中环 01',region:'hk',provider:'主订阅'},
      {id:'kr1',name:'韩国 · 首尔 01',region:'kr',provider:'备用订阅'},
      {id:'tw1',name:'台湾 · 台北 01',region:'tw',provider:'主订阅'},
      {id:'us1',name:'美国 · 洛杉矶 01',region:'us',provider:'备用订阅'}
    ];
    const initialSites = [
      {id:'chatgpt',name:'ChatGPT',url:'https://chatgpt.com/cdn-cgi/trace',statuses:[200],locked:true},
      {id:'github',name:'GitHub',url:'https://github.com/',statuses:[200]},
      {id:'google',name:'Google',url:'https://www.google.com/generate_204',statuses:[204]},
      {id:'youtube',name:'YouTube',url:'https://www.youtube.com/',statuses:[200]},
      {id:'wikipedia',name:'Wikipedia',url:'https://www.wikipedia.org/',statuses:[200]}
    ];
    return {
      screen:'idle',connected:false,sites:initialSites,selectedSites:['chatgpt'],regions:['jp','sg'],
      regionList:[{id:'jp',name:'日本'},{id:'sg',name:'新加坡'},{id:'hk',name:'香港'},{id:'kr',name:'韩国'},{id:'tw',name:'台湾'},{id:'us',name:'美国'},{id:'other',name:'其他'}],
      group:'',provider:'',include:'',exclude:'',limit:0,rounds:3,workers:4,timeout:8,advanced:false,manualNodes:[],nodeDraft:[],nodeSearch:'',
      modal:'',modalError:'',pendingDelete:'',siteDraft:{id:'',name:'',url:'',statuses:'200'},
      connMode:'auto',connection:{binary:'',config:'',directory:'',controller:'',pipe:'',interface:''},detected:false,
      format:'csv',includeFailures:true,sort:'latency',sortDirection:1,activeSite:'chatgpt',report:null,progress:6,total:24,liveTimer:null,
      toast:'',toastError:false,toastTimer:null,tabLeft:0,tabWidth:100,detailRow:null,runNodes:[],runSites:[],opener:null,
      init() {
        const preset = new URLSearchParams(location.search).get('state') || document.body.dataset.start || 'idle';
        this.restoreSettings();
        if (preset !== 'idle') {
          this.connected = !['error','connection'].includes(preset);
          this.selectedSites = ['chatgpt','github'];
        }
        if (['done','stopped','detail','export'].includes(preset)) this.makeReport();
        this.screen = ['running','done','stopped','empty','error'].includes(preset) ? preset : 'idle';
        if (preset === 'empty') this.regions = ['other'];
        if (['connection','sites','site-edit','nodes','detail','export'].includes(preset)) {
          if (preset === 'detail') this.detailRow = this.report.rows.find(r => r.site_id === 'chatgpt' && r.id === 'sg2');
          if (preset === 'nodes') this.nodeDraft = ['jp1','sg1'];
          this.$nextTick(() => this.openModal(preset, true));
        }
        this.$watch('activeSite', () => this.$nextTick(() => this.measureTab()));
        this.$nextTick(() => this.measureTab());
        window.addEventListener('resize', () => this.measureTab());
        window.addEventListener('pagehide', () => {clearInterval(this.liveTimer);clearTimeout(this.toastTimer)});
      },
      get matchedNodes() {
        const includes = this.include.split(',').map(s=>s.trim().toLowerCase()).filter(Boolean);
        const excludes = this.exclude.split(',').map(s=>s.trim().toLowerCase()).filter(Boolean);
        let list = nodeList.filter(n => (!this.regions.length || this.regions.includes(n.region)) &&
          (!this.provider || n.provider === this.provider) &&
          (!this.group || (this.group === 'Asia' ? n.region !== 'us' : true)) &&
          (!includes.length || includes.some(s => n.name.toLowerCase().includes(s))) &&
          !excludes.some(s => n.name.toLowerCase().includes(s)));
        return this.limit > 0 ? list.slice(0,Number(this.limit)) : list;
      },
      get candidates() {return this.matchedNodes.filter(n => !this.manualNodes.length || this.manualNodes.includes(n.id))},
      get visibleNodes() {return this.matchedNodes.filter(n => n.name.toLowerCase().includes(this.nodeSearch.toLowerCase()))},
      get reportSites() {return this.report ? this.report.sites : this.sites.filter(s=>this.selectedSites.includes(s.id))},
      get rows() {
        let rows = this.report ? this.report.rows.filter(r=>r.site_id===this.activeSite) : [];
        if (this.screen === 'running') {
          const source = this.runNodes.length ? this.runNodes : this.candidates;
          const site = this.sites.find(s=>s.id===this.activeSite) || this.sites[0];
          const websites=this.runSites.length?this.runSites:this.sites.filter(s=>this.selectedSites.includes(s.id));
          const siteIndex=Math.max(0,websites.findIndex(s=>s.id===site.id));
          const done=Math.max(0,Math.floor((this.progress-siteIndex*source.length*Number(this.rounds))/Number(this.rounds)));
          rows = source.slice(0,done).map(n=>this.makeRow(n,site));
        }
        return [...rows].sort((a,b)=>(a.successes===a.total?0:1)-(b.successes===b.total?0:1) ||
          (this.sort==='name'?a.name.localeCompare(b.name,'zh'):(a.median_ms ?? 9999)-(b.median_ms ?? 9999))*this.sortDirection);
      },
      get recommendation() {
        if (!this.report || this.screen === 'running') return null;
        return this.rows.filter(r=>r.successes===r.total).sort((a,b)=>a.median_ms-b.median_ms)[0] || null;
      },
      get modalTitle() {return {'connection':'连接设置','sites':'网站管理','site-edit':this.siteDraft.id?'编辑网站':'添加网站','nodes':'选择测速节点','detail':'请求详情','export':'导出报告'}[this.modal] || ''},
      get hasRows() {return this.rows.length > 0},
      get running() {return this.screen === 'running'},
      regionName(id) {return this.regionList.find(r=>r.id===id)?.name || '其他'},
      ms(value) {return value == null ? '—' : value.toFixed(1) + ' ms'},
      toggleRegion(id) {this.regions = this.regions.includes(id) ? this.regions.filter(r=>r!==id) : [...this.regions,id]},
      notify(text,error=false) {clearTimeout(this.toastTimer);this.toast=text;this.toastError=error;this.toastTimer=setTimeout(()=>this.toast='',4200)},
      refresh() {this.connected=true;this.detected=true;if(this.screen==='error')this.screen='idle';this.notify('已读取 8 个可测节点')},
      openModal(kind,preset=false) {
        this.opener=document.activeElement;this.modalError='';this.pendingDelete='';
        if(kind==='nodes'&&!preset) {this.nodeDraft=[...this.manualNodes];this.nodeSearch='';if(!this.connected)this.refresh()}
        if(kind==='connection')this.detected=this.connected;
        this.modal=kind;
        this.$nextTick(()=>{if(!this.$refs.dialog.open)this.$refs.dialog.showModal();this.$refs.dialog.querySelector('[data-autofocus]')?.focus()});
      },
      closeModal() {this.$refs.dialog.close();this.modal='';this.modalError='';this.opener?.focus();this.$nextTick(()=>this.measureTab())},
      saveSettings(silent=false) {
        try {
          const value={sites:this.sites,selectedSites:this.selectedSites,regions:this.regions,group:this.group,provider:this.provider,include:this.include,exclude:this.exclude,limit:this.limit,rounds:this.rounds,workers:this.workers,timeout:this.timeout,manualNodes:this.manualNodes,connection:this.connection,connMode:this.connMode};
          localStorage.setItem('site-probe-prototype-v1',JSON.stringify(value));
          if(!silent)this.notify('网站与筛选设置已保存');
          return true;
        } catch(e) {this.notify('设置保存失败，当前填写内容已保留',true);return false}
      },
      restoreSettings() {
        try {
          const value=JSON.parse(localStorage.getItem('site-probe-prototype-v1')||'null');
          if(!value || !Array.isArray(value.sites) || !Array.isArray(value.regions))return;
          for(const key of ['sites','selectedSites','regions','group','provider','include','exclude','limit','rounds','workers','timeout','manualNodes','connection','connMode'])if(value[key]!==undefined)this[key]=value[key];
        } catch(e) {}
      },
      makeRow(node,site) {
        const base={jp1:318.4,jp2:427.8,sg1:362.1,sg2:694.6,hk1:282.7,kr1:401.9,tw1:352.3,us1:785.8};
        let latency=base[node.id]||453.7;
        if(site.id==='github')latency+=node.id==='sg1'?-159.4:96.2;
        const failed=node.id==='sg2';
        const count=Number(this.rounds);
        const successes=failed?Math.max(0,count-1):count;
        const wantedJitter=node.id==='jp1'?14.2:node.id==='sg1'?19.8:39.7;
        const rawOffsets=Array.from({length:successes},(_,i)=>i-(successes-1)/2);
        const offsetScale=successes>1?Math.sqrt(rawOffsets.reduce((sum,v)=>sum+v*v,0)/successes):1;
        const values=rawOffsets.map(offset=>latency+offset*wantedJitter/offsetScale);
        return {...node,site_id:site.id,site_name:site.name,url:site.url,total:count,successes,median_ms:successes?latency:null,jitter_ms:successes?(successes>1?wantedJitter:0):null,
          samples:Array.from({length:count},(_,i)=>({round:i+1,ok:!(failed&&i===count-1),status:failed&&i===count-1?0:site.statuses[0],ttfb_ms:failed&&i===count-1?null:values[i],total_ms:failed&&i===count-1?null:values[i]+41.7,reason:failed&&i===count-1?'请求超时':'通过校验'}))};
      },
      makeReport(nodes,sites) {
        const targets=nodes || this.candidates;
        const websites=sites || this.sites.filter(s=>this.selectedSites.includes(s.id));
        this.report={sites:JSON.parse(JSON.stringify(websites)),rows:targets.flatMap(n=>websites.map(s=>this.makeRow(n,s))),requests:targets.length*websites.length*Number(this.rounds),nodes:targets.length,time:'10:24:36'};
        this.activeSite=websites[0]?.id || 'chatgpt';
      },
      startRun() {
        if(!this.selectedSites.length){this.notify('请至少选择一个测试网站',true);return}
        if(!this.candidates.length){this.screen='empty';this.notify('当前条件没有匹配节点',true);return}
        if(!this.connected)this.refresh();
        if(!this.saveSettings(true))return;
        this.runNodes=JSON.parse(JSON.stringify(this.candidates));
        this.runSites=JSON.parse(JSON.stringify(this.sites.filter(s=>this.selectedSites.includes(s.id))));
        this.activeSite=this.runSites[0].id;this.progress=0;this.total=this.runNodes.length*this.runSites.length*Number(this.rounds);
        this.screen='running';this.$nextTick(()=>this.measureTab());clearInterval(this.liveTimer);
        this.liveTimer=setInterval(()=>{
          this.progress=Math.min(this.total,this.progress+3);
          if(this.progress===this.total){clearInterval(this.liveTimer);this.liveTimer=null;this.makeReport(this.runNodes,this.runSites);this.screen='done';this.notify('测速完成，可按网站查看推荐节点');this.$nextTick(()=>this.measureTab())}
        },450);
      },
      stopRun() {clearInterval(this.liveTimer);this.liveTimer=null;this.screen='stopped';this.notify(this.report?'已停止，上次完整报告已保留':'已停止，本次未生成完整报告')},
      showDetail(row) {this.detailRow=row;this.openModal('detail')},
      measureTab() {
        const button=this.$refs.tabs?.querySelector('[aria-selected="true"]');
        if(button){this.tabLeft=button.offsetLeft;this.tabWidth=button.offsetWidth}
      },
      toggleSort(key) {this.sortDirection=this.sort===key?-this.sortDirection:1;this.sort=key},
      selectVisible() {this.nodeDraft=[...new Set([...this.nodeDraft,...this.visibleNodes.map(n=>n.id)])]},
      applyNodes() {this.manualNodes=[...this.nodeDraft];this.closeModal();this.notify(this.manualNodes.length?'已限定为 '+this.manualNodes.length+' 个节点':'已恢复为全部匹配节点')},
      editSite(site=null) {this.siteDraft=site?{id:site.id,name:site.name,url:site.url,statuses:site.statuses.join(',')}:{id:'',name:'',url:'',statuses:'200'};this.modalError='';this.modal='site-edit';this.$nextTick(()=>this.$refs.siteName.focus())},
      applySite() {
        this.modalError='';
        const name=this.siteDraft.name.trim(),text=this.siteDraft.url.trim();
        if(!name){this.modalError='请填写网站名称';return}
        if(this.sites.some(site=>site.id!==this.siteDraft.id&&site.name.toLowerCase()===name.toLowerCase())){this.modalError='已存在同名网站，请使用不同名称';return}
        let url;try{url=new URL(text)}catch(e){this.modalError='请输入完整的 HTTP 或 HTTPS 地址';return}
        if(!['http:','https:'].includes(url.protocol)||url.username||url.password){this.modalError='仅支持不含用户名和密码的 HTTP / HTTPS 地址';return}
        const statuses=this.siteDraft.statuses.split(',').map(s=>s.trim());
        if(statuses.some(s=>!/^\d{3}$/.test(s)||Number(s)<100||Number(s)>599)){this.modalError='状态码应为 100–599，用英文逗号分隔';return}
        const id=this.siteDraft.id||'custom-'+Date.now();
        const item={id,name,url:url.href,statuses:[...new Set(statuses.map(Number))]};
        const before=JSON.parse(JSON.stringify(this.sites));
        if(this.siteDraft.id)this.sites=this.sites.map(s=>s.id===id?item:s);else this.sites=[...this.sites,item];
        if(!this.saveSettings(true)){this.sites=before;this.modalError='保存失败，填写内容已保留，请重试';return}
        if(!this.selectedSites.includes(id))this.selectedSites=[...this.selectedSites,id];
        this.saveSettings(true);this.modal='sites';this.notify('网站已保存');
      },
      removeSite(id) {
        const before=JSON.parse(JSON.stringify(this.sites)),selected=[...this.selectedSites];
        this.sites=this.sites.filter(s=>s.id!==id);this.selectedSites=this.selectedSites.filter(s=>s!==id);
        if(!this.saveSettings(true)){this.sites=before;this.selectedSites=selected;return}
        this.pendingDelete='';this.notify('网站已移除');
      },
      detectConnection() {this.detected=true;this.notify('已发现 Clash Verge Rev')},
      saveConnection() {
        if(this.connMode==='manual'&&(!this.connection.binary.trim()||!this.connection.config.trim())){this.modalError='请填写内核与配置文件路径';return}
        if(!this.saveSettings(true)){this.modalError='保存失败，路径已保留，请重试';return}
        this.connected=this.detected||this.connMode==='manual';this.closeModal();this.notify('连接设置已保存');
      },
      browse(key) {
        const input=document.createElement('input');input.type='file';
        input.accept=key==='binary'?'.exe':'.yaml,.yml,.json';
        input.onchange=()=>{if(input.files[0]){this.connection[key]=input.files[0].name;this.notify('已选中 '+input.files[0].name)}};
        input.click();
      },
      exportReport() {
        if(!this.report)return;
        const rows=this.includeFailures?this.report.rows:this.report.rows.filter(r=>r.successes===r.total);
        let content;
        if(this.format==='json')content=JSON.stringify({...this.report,rows},null,2);
        else {
          const cell=v=>'"'+String(v??'').replaceAll('"','""')+'"';
          content='\uFEFF'+[['节点','地区','网站','成功次数','轮数','首字节(ms)','波动(ms)'],...rows.map(r=>[r.name,this.regionName(r.region),r.site_name,r.successes,r.total,r.median_ms,r.jitter_ms])].map(row=>row.map(cell).join(',')).join('\r\n');
        }
        const blob=new Blob([content],{type:this.format==='csv'?'text/csv;charset=utf-8':'application/json'});
        const url=URL.createObjectURL(blob),link=document.createElement('a');
        link.href=url;link.download='ProxySprint · 代理节点测速-报告.'+this.format;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
        this.closeModal();this.notify('已导出 '+this.format.toUpperCase()+' 报告');
      }
    };
  });
});
