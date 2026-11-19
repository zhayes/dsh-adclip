window.__ModuleLoader__.load({
  id: '@local/dsh-adclip',
  factory(require) {
    const React = require('react')
    const h = React.createElement
    const { useState, useEffect, useRef, useCallback } = React

    const boot = window.__ADPLUS_STUDIO__ || {}
    const IS_MAC = typeof navigator !== 'undefined' && /Mac/i.test(navigator.platform || navigator.userAgent)
    const API = boot.base || '/adplus/api'
    const MEDIA = boot.media || '/adplus/media'
    let TOKEN = boot.token || ''

    async function tokenReady() {
      if (TOKEN) return TOKEN
      try {
        const res = await fetch('/adplus/health')
        const data = await res.json()
        if (data && data.token) TOKEN = data.token
      } catch { /* the refreshed host injects the token instead */ }
      return TOKEN
    }

    const CSS = `
.adp-root.adp-mac .adp-top{padding-left:max(150px,env(safe-area-inset-left) + 138px)}
.adp-root.adp-mac .adp-brand{display:none}
.adp-root.adp-mac .adp-tabs{margin-left:0}
.adp-root.adp-mac.adp-sidebar-open .adp-top{padding-left:max(20px,env(safe-area-inset-left) + 12px)}
.adp-root.adp-mac.adp-sidebar-open .adp-brand{display:flex}
.adp-root.adp-mac.adp-sidebar-open .adp-tabs{margin-left:10px}
.adp-root{height:100%;min-height:520px;display:flex;flex-direction:column;overflow:hidden;background:var(--dsw-alias-bg-base);color:var(--dsw-alias-label-primary);font:13px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text","PingFang SC",sans-serif;font-variant-numeric:tabular-nums}
.adp-top{display:flex;align-items:center;gap:14px;padding:0 20px 0 max(20px,env(safe-area-inset-left) + 12px);height:54px;box-sizing:border-box;overflow:hidden;border-bottom:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-1);flex:0 0 auto;min-width:0;position:relative;z-index:2}
.adp-brand{font-weight:750;letter-spacing:-.3px;font-size:15px;display:inline-flex;align-items:center;gap:5px;flex:0 0 auto;white-space:nowrap;min-width:max-content;line-height:1;height:auto}
.adp-brand:after{content:"";width:5px;height:5px;border-radius:50%;background:#E5B45C;display:inline-block}
.adp-sub{color:var(--dsw-alias-label-secondary);font:10px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;flex:0 1 auto;min-width:0;max-width:210px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;align-items:center;height:auto;line-height:1.2}
.adp-tabs{display:flex;gap:2px;margin-left:10px;height:100%;align-items:stretch;flex:0 1 auto;min-width:0;overflow-x:auto;scrollbar-width:none}
.adp-tabs::-webkit-scrollbar{display:none}
.adp-tab{flex:0 0 auto}
.adp-tab{border:0;background:transparent;color:var(--dsw-alias-label-secondary);padding:0 12px;cursor:pointer;font:inherit;position:relative;height:100%}
.adp-tab:hover{color:var(--dsw-alias-label-primary)}
.adp-tab.on{color:var(--dsw-alias-label-primary);font-weight:650}
.adp-tab.on:after{content:"";position:absolute;left:12px;right:12px;bottom:-1px;height:2px;background:#E5B45C;border-radius:2px 2px 0 0}
.adp-grow{flex:1 1 auto;min-width:0}
.adp-body{flex:1 1 auto;min-height:0;overflow:auto;padding:22px 24px 40px}
.adp-page{max-width:1120px;margin:0 auto}
.adp-page-head{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin:2px 0 16px}
.adp-eyebrow{font:10px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.12em;text-transform:uppercase;color:#C99B54;margin-bottom:5px}
.adp-title{font-size:24px;line-height:1.12;font-weight:750;letter-spacing:-.5px;margin:0}
.adp-lede{color:var(--dsw-alias-label-secondary);font-size:12.5px;margin:6px 0 0;max-width:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.adp-lede.adp-nowrap{max-width:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.adp-page-meta{display:flex;align-items:center;gap:8px;color:var(--dsw-alias-label-secondary);font-size:11px;padding-bottom:2px}
.adp-panel{border:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-1);border-radius:14px;overflow:hidden;box-shadow:0 1px 0 rgba(255,255,255,.03) inset}
.adp-panel-grid{display:grid;grid-template-columns:360px minmax(0,1fr)}
.adp-asset-col{padding:18px;border-right:1px solid var(--dsw-alias-border-l1);background:linear-gradient(180deg,var(--dsw-alias-bg-layer-2),var(--dsw-alias-bg-layer-1));min-width:0}
.adp-form-col{padding:18px 20px 0;min-width:0}
.adp-section-head{display:flex;align-items:center;gap:8px;margin:0 0 9px}
.adp-section-head:not(:first-child){margin-top:20px}
.adp-step{font:10px/1 ui-monospace,SFMono-Regular,Menlo,monospace;color:#C99B54;letter-spacing:.06em;border:1px solid rgba(229,180,92,.35);border-radius:4px;padding:3px 4px;background:rgba(229,180,92,.06)}
.adp-section-title{font-size:12.5px;font-weight:700;letter-spacing:.01em}
.adp-section-note{font-size:10.5px;color:var(--dsw-alias-label-secondary);margin-left:auto}
.adp-label{display:flex;align-items:center;justify-content:space-between;gap:8px;font:10.5px/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.05em;text-transform:uppercase;color:var(--dsw-alias-label-secondary);margin:0 0 5px}
.adp-label .count{font-weight:400;letter-spacing:0;text-transform:none;color:var(--dsw-alias-label-secondary);opacity:.8}
.adp-drop{position:relative;border:1px dashed var(--dsw-alias-border-l2);border-radius:11px;background:var(--dsw-alias-bg-layer-2);min-height:198px;display:flex;align-items:center;justify-content:center;cursor:pointer;overflow:hidden;transition:border-color .15s ease,background .15s ease}
.adp-drop:hover,.adp-drop.drag{border-color:#C99B54;background:color-mix(in srgb,var(--dsw-alias-bg-layer-2) 86%,#E5B45C 14%)}
.adp-drop video{width:100%;height:198px;object-fit:contain;display:block;background:#08090d}
.adp-drop .adp-drop-empty{display:flex;flex-direction:column;align-items:center;gap:5px;color:var(--dsw-alias-label-secondary);text-align:center;padding:16px}
.adp-drop .adp-drop-empty b{font-size:12.5px;color:var(--dsw-alias-label-primary);font-weight:600}
.adp-drop .adp-drop-empty span{font-size:10.5px;line-height:1.5}
.adp-drop .adp-drop-overlay{position:absolute;left:0;right:0;bottom:0;padding:8px 9px;background:linear-gradient(transparent,rgba(0,0,0,.72));color:#fff;font-size:10.5px;display:flex;align-items:center;justify-content:space-between;gap:8px}
.adp-drop .adp-remove{background:rgba(0,0,0,.45);color:#fff;border:0;border-radius:5px;width:20px;height:20px;cursor:pointer;line-height:18px;font-size:14px}
.adp-media-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}
.adp-media{position:relative;aspect-ratio:1/1;border:1px solid var(--dsw-alias-border-l1);border-radius:8px;overflow:hidden;background:var(--dsw-alias-bg-layer-2)}
.adp-media img{width:100%;height:100%;object-fit:cover;display:block}
.adp-media .adp-remove{position:absolute;top:3px;right:3px;width:18px;height:18px;border:0;border-radius:50%;background:rgba(0,0,0,.55);color:#fff;font-size:12px;line-height:18px;cursor:pointer;opacity:0;transition:opacity .15s ease}
.adp-media:hover .adp-remove{opacity:1}
.adp-media-add{aspect-ratio:1/1;border:1px dashed var(--dsw-alias-border-l2);border-radius:8px;background:transparent;color:var(--dsw-alias-label-secondary);display:flex;align-items:center;justify-content:center;flex-direction:column;gap:2px;cursor:pointer;font:10px/1.2 inherit}
.adp-media-add:hover{border-color:#C99B54;color:var(--dsw-alias-label-primary)}
.adp-media-add b{font-size:16px;font-weight:300}
.adp-form-col .adp-textarea{min-height:104px;resize:vertical;padding:10px 11px;line-height:1.55;font-size:12.5px}
.adp-brief{border:1px solid var(--dsw-alias-border-l1);border-radius:10px;background:var(--dsw-alias-bg-layer-2);overflow:hidden;transition:border-color .15s ease,box-shadow .15s ease}
.adp-brief:focus-within{border-color:#C99B54;box-shadow:0 0 0 2px rgba(229,180,92,.13)}
.adp-brief-head{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:8px 11px;border-bottom:1px solid var(--dsw-alias-border-l1);font:10px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.06em;text-transform:uppercase;color:var(--dsw-alias-label-secondary)}
.adp-brief-head b{font-weight:600;color:var(--dsw-alias-label-primary);letter-spacing:.04em}
.adp-brief-input{display:block;width:100%;min-height:92px;max-height:190px;resize:vertical;border:0;outline:0;background:transparent;color:var(--dsw-alias-label-primary);padding:10px 11px;font:12.5px/1.6 inherit;box-sizing:border-box}
.adp-brief-input::placeholder{color:var(--dsw-alias-label-secondary);opacity:.82}
.adp-brief-foot{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:7px 11px;border-top:1px solid var(--dsw-alias-border-l1);color:var(--dsw-alias-label-secondary);font-size:10.5px;line-height:1.4}
.adp-key{font:9.5px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;border:1px solid var(--dsw-alias-border-l1);border-radius:4px;padding:2px 5px;color:var(--dsw-alias-label-secondary);background:var(--dsw-alias-bg-layer-1);white-space:nowrap}
.adp-hint{font-size:10.5px;color:var(--dsw-alias-label-secondary);line-height:1.5;margin:5px 0 0}
.adp-check{display:flex;align-items:center;gap:7px;color:var(--dsw-alias-label-secondary);font-size:11px;margin-top:10px;cursor:pointer}
.adp-check input{accent-color:#C99B54;width:13px;height:13px;margin:0}
.adp-field-grid{display:grid;gap:9px}
.adp-field-grid.g3{grid-template-columns:repeat(3,minmax(0,1fr))}
.adp-field-grid.g4{grid-template-columns:repeat(4,minmax(0,1fr))}
.adp-field-grid.g2{grid-template-columns:repeat(2,minmax(0,1fr))}
.adp-field{min-width:0}
.adp-field .adp-select{width:100%;height:31px;padding:0 8px;border-radius:7px;font-size:11.5px;background:var(--dsw-alias-bg-layer-2)}
.adp-field .adp-input{width:100%;height:31px;padding:0 8px;border-radius:7px;font-size:11.5px;background:var(--dsw-alias-bg-layer-2)}
.adp-field .adp-textarea{width:100%;background:var(--dsw-alias-bg-layer-2)}
.adp-field-label{font:10px/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.04em;text-transform:uppercase;color:var(--dsw-alias-label-secondary);margin:0 0 4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.adp-actionbar{display:flex;align-items:center;gap:12px;margin:18px -20px 0;padding:13px 20px;border-top:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-2)}
.adp-action-note{font-size:10.5px;color:var(--dsw-alias-label-secondary);line-height:1.45}
.adp-primary{border:0;border-radius:8px;background:var(--dsw-alias-label-primary);color:var(--dsw-alias-bg-base);padding:9px 16px;font:inherit;font-weight:700;font-size:12px;cursor:pointer;display:inline-flex;align-items:center;gap:8px;white-space:nowrap}
.adp-primary:hover{opacity:.88}
.adp-primary:focus-visible,.adp-btn:focus-visible,.adp-drop:focus-visible,.adp-media-add:focus-visible{outline:2px solid #C99B54;outline-offset:2px}
.adp-primary:disabled{opacity:.38;cursor:not-allowed}
.adp-primary .arrow{font-size:14px;line-height:1;font-weight:400}
.adp-card{border:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-1);border-radius:12px;padding:14px}
.adp-row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.adp-col{display:flex;flex-direction:column;gap:8px}
.adp-muted{color:var(--dsw-alias-label-secondary)}
.adp-faint{color:var(--dsw-alias-label-secondary);opacity:.75}
.adp-h1{font-size:18px;font-weight:700;letter-spacing:-.2px;margin:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.adp-h2{font-size:12.5px;font-weight:700;margin:0}
.adp-small{font-size:11px}
.adp-btn{border:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-2);color:var(--dsw-alias-label-primary);border-radius:7px;padding:5px 9px;cursor:pointer;font:inherit;font-size:11.5px}
.adp-btn:hover{filter:brightness(1.08)}
.adp-btn.primary{background:var(--dsw-alias-label-primary);border-color:transparent;color:var(--dsw-alias-bg-base);font-weight:650}
.adp-btn.ghost{background:transparent}
.adp-btn.danger{color:var(--dsw-alias-state-error-primary)}
.adp-btn:disabled{opacity:.45;cursor:not-allowed}
.adp-input,.adp-select,.adp-textarea{border:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-2);color:var(--dsw-alias-label-primary);border-radius:7px;padding:7px 8px;font:inherit;min-width:0;outline:none}
.adp-input:focus,.adp-select:focus,.adp-textarea:focus{border-color:#C99B54;box-shadow:0 0 0 2px rgba(229,180,92,.15)}
.adp-textarea{width:100%;min-height:90px;resize:vertical}
.adp-select{min-width:84px}
.adp-error{color:var(--dsw-alias-state-error-primary);font-size:11px;line-height:1.45;white-space:pre-wrap}
.adp-badge{font:10px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace;border-radius:999px;padding:2px 7px;border:1px solid var(--dsw-alias-border-l1);color:var(--dsw-alias-label-secondary);letter-spacing:.02em}
.adp-caps{display:inline-flex;gap:4px;flex-wrap:wrap}
.adp-cap{font-size:10px;line-height:1.5;padding:0 5px;border-radius:4px;border:1px solid var(--dsw-alias-border-l1);color:var(--dsw-alias-label-secondary);background:var(--dsw-alias-bg-layer-2);white-space:nowrap}
.adp-badge.ok{color:var(--dsw-alias-state-success-primary);border-color:color-mix(in srgb,var(--dsw-alias-state-success-primary) 55%,transparent)}
.adp-badge.warn{color:var(--dsw-alias-state-warn-primary);border-color:color-mix(in srgb,var(--dsw-alias-state-warn-primary) 55%,transparent)}
.adp-badge.bad{color:var(--dsw-alias-state-error-primary);border-color:color-mix(in srgb,var(--dsw-alias-state-error-primary) 55%,transparent)}
.adp-progress{height:6px;background:#26272d;border:1px solid rgba(255,255,255,.05);border-radius:999px;overflow:hidden;box-shadow:inset 0 1px 2px rgba(0,0,0,.35)}
.adp-progress i{display:block;height:100%;background:linear-gradient(90deg,#b8843e,#e2c08a);transition:width .3s ease}
.adp-video-wrap{display:flex;justify-content:center;align-items:center;background:#000;border-radius:9px;overflow:hidden;min-height:220px}
.adp-video{max-width:100%;max-height:520px;width:auto;background:#000;display:block}
.adp-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px}
.adp-task-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;align-items:start}
@media(max-width:980px){.adp-task-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:640px){.adp-task-grid{grid-template-columns:1fr}}
.adp-run-card{position:relative;min-height:0;padding:12px 13px 12px;display:flex;flex-direction:column;gap:3px}
.adp-task-head{display:flex;align-items:flex-start;gap:7px;min-width:0}
.adp-task-check{margin-top:4px}
.adp-task-check-spacer{width:14px;height:14px;flex:0 0 auto;margin-top:4px}
.adp-task-title{flex:1;min-width:0;font-size:12.5px;font-weight:650;line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:35px;overflow-wrap:anywhere}
.adp-task-title-input{height:28px;font-size:12px;min-width:0}
.adp-task-edit{flex:0 0 auto;width:23px;height:23px;margin-top:-2px}
.adp-task-save{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;padding:0;border:0;border-radius:50%;background:transparent;color:var(--dsw-alias-label-secondary);cursor:pointer}
.adp-task-save:hover{background:rgba(201,155,84,.14);color:#E2B96F}
.adp-task-save.ok{color:#C99B54}
.adp-task-scenario{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-left:21px;padding-right:56px;line-height:1.5}
.adp-task-time{line-height:1.5;padding-left:21px;padding-right:56px;font-variant-numeric:tabular-nums}
.adp-task-progress{margin:6px 0 0 21px}
.adp-status-stamp{position:absolute;right:14px;top:56px;width:44px;height:44px;aspect-ratio:1/1;min-width:44px;min-height:44px;display:flex;align-items:center;justify-content:center;text-align:center;font-family:Georgia,"Songti SC",serif;transform:rotate(-8deg);opacity:.62;pointer-events:none;mix-blend-mode:screen;border-radius:50%;z-index:2}
.adp-status-stamp .stamp-ring{position:absolute;inset:0;width:100%;height:100%;overflow:visible}
.adp-status-stamp b{position:relative;z-index:1;font-size:10px;line-height:1;letter-spacing:.1em;font-weight:700}
.adp-status-stamp.ok{color:#8FCB9B}.adp-status-stamp.bad{color:#E38B8B}.adp-status-stamp.warn{color:#D7B36A}.adp-status-stamp.muted{color:#8A8E99}
.adp-run-card.selected{border-color:#C99B54;box-shadow:0 0 0 1px #C99B54 inset}
.adp-task-check{accent-color:#C99B54;width:14px;height:14px;margin:0;cursor:pointer}
.adp-toolbar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;border:1px solid var(--dsw-alias-border-l1);border-radius:10px;background:var(--dsw-alias-bg-layer-1);padding:9px 10px;margin:12px 0}
.adp-toolbar .adp-input,.adp-toolbar .adp-select,.adp-toolbar .adp-btn{height:32px;box-sizing:border-box;font-size:11px}
.adp-toolbar .adp-input,.adp-toolbar .adp-select{padding-top:0;padding-bottom:0}
.adp-toolbar .adp-select{padding-right:28px}
.adp-toolbar .adp-date-input{padding:0 8px}
.adp-toolbar .adp-btn{display:inline-flex;align-items:center;justify-content:center;padding:0 10px;line-height:1}
.adp-pager{display:flex;align-items:center;justify-content:center;gap:12px;margin:14px 0 0}
.adp-asset-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin-top:12px}
.adp-asset-card{border:1px solid var(--dsw-alias-border-l1);border-radius:10px;background:var(--dsw-alias-bg-layer-1);padding:8px;min-width:0}
.adp-asset-card>img,.adp-asset-card>video{width:100%;height:110px;object-fit:cover;border-radius:7px;display:block;background:#0a0b10}
.adp-asset-card-body{display:flex;align-items:center;gap:6px;margin-top:6px;min-width:0}
.adp-asset-card-body>.adp-grow{display:block;flex:1 1 auto;width:0;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.adp-asset-card-body .adp-icon-btn{width:28px;height:28px;flex:0 0 auto}
.adp-asset-meta-row{display:flex;align-items:center;justify-content:space-between;gap:6px;margin-top:4px;min-width:0;font-size:9.5px;line-height:1.4;color:var(--dsw-alias-label-tertiary)}
.adp-asset-kind{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.adp-asset-time{flex:0 0 auto;white-space:nowrap;font-variant-numeric:tabular-nums;color:var(--dsw-alias-label-tertiary)}
.adp-run-card{border:1px solid var(--dsw-alias-border-l1);border-radius:9px;padding:10px;background:var(--dsw-alias-bg-layer-2);cursor:pointer}
.adp-run-card:hover{border-color:#C99B54}
.adp-sb{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:9px}
.adp-sb-card{border:1px solid var(--dsw-alias-border-l1);border-radius:9px;overflow:hidden;background:var(--dsw-alias-bg-layer-2);cursor:pointer}
.adp-sb-card.on{border-color:#C99B54;box-shadow:0 0 0 1px #C99B54 inset}
.adp-sb-card img{width:100%;height:108px;object-fit:cover;display:block;background:#111}
.adp-sb-meta{padding:7px 8px;display:flex;flex-direction:column;gap:3px}
.adp-chat{display:flex;flex-direction:column;gap:8px;max-height:280px;overflow:auto;padding:2px}
.adp-drop.has-preview{cursor:zoom-in}
.adp-drop-actions{display:flex;align-items:center;gap:4px;flex:0 0 auto}
.adp-drop-action{height:22px;padding:0 7px;font-size:10px;background:rgba(0,0,0,.45);border-color:rgba(255,255,255,.22);color:#fff}
.adp-media.has-preview{cursor:zoom-in}
.adp-thread{display:flex;flex-direction:column;gap:9px;max-height:52vh;min-height:280px;overflow:auto;padding:12px 0 2px;margin-bottom:10px}
.adp-create-thread{min-height:340px;max-height:none}
.adp-thread-empty{border:1px dashed var(--dsw-alias-border-l2);border-radius:10px;background:var(--dsw-alias-bg-layer-1);padding:22px 18px;text-align:center;display:flex;flex-direction:column;gap:7px;color:var(--dsw-alias-label-secondary)}
.adp-thread-empty b{font-size:12.5px;color:var(--dsw-alias-label-primary);font-weight:650}
.adp-thread-empty span{font-size:10.5px;line-height:1.6;max-width:520px;margin:0 auto}
.adp-thread .adp-msg{max-width:min(680px,92%);align-self:flex-start}
.adp-thread .adp-msg.user{align-self:flex-end}
.adp-confirm-dock{flex:0 0 auto;padding:0 0 8px}
.adp-confirm-card{border:1px solid rgba(201,155,84,.45);border-radius:14px;background:linear-gradient(180deg,rgba(201,155,84,.1),var(--dsw-alias-bg-layer-2));padding:11px 13px;display:flex;flex-direction:column;gap:8px;box-shadow:0 10px 26px rgba(0,0,0,.26)}
.adp-confirm-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px}
.adp-confirm-tag{font:10px/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.08em;color:#C99B54;white-space:nowrap}
.adp-confirm-head b{font-size:12px;font-weight:650;color:var(--dsw-alias-label-primary);font-variant-numeric:tabular-nums}
.adp-confirm-brief{padding-top:7px;border-top:1px solid var(--dsw-alias-border-l1);font-size:11px;line-height:1.55;color:var(--dsw-alias-label-secondary);max-height:74px;overflow:auto;white-space:pre-wrap}
.adp-confirm-actions{display:flex;gap:8px;justify-content:flex-end}
.adp-chatpage .adp-msg.sys{align-self:center;max-width:100%;font-size:10.5px;line-height:1.5;color:var(--dsw-alias-label-secondary);text-align:center}
.adp-chat-actions{display:flex;align-items:center;gap:8px;flex:0 0 auto}
.adp-chat-actions .adp-btn{display:inline-flex;align-items:center;justify-content:center;line-height:0;width:32px;height:32px;padding:0;color:var(--dsw-alias-label-secondary)}
.adp-chat-actions .adp-btn svg{display:block}
.adp-chat-actions .adp-btn:hover:not(:disabled){color:var(--dsw-alias-label-primary)}
.adp-history-modal{width:min(560px,94vw)}
.adp-history-list{display:flex;flex-direction:column;gap:8px}
.adp-history-row{display:flex;align-items:stretch;gap:6px;padding:9px 10px;border:1px solid var(--dsw-alias-border-l1);border-radius:10px;background:var(--dsw-alias-bg-layer-2)}
.adp-history-row.active{border-color:rgba(201,155,84,.55)}
.adp-history-open{flex:1 1 auto;min-width:0;display:flex;flex-direction:column;gap:3px;text-align:left;background:none;border:0;padding:0;color:inherit;cursor:pointer}
.adp-history-open b{font-size:12.5px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.adp-history-open span{font-size:10.5px;color:var(--dsw-alias-label-secondary)}
.adp-composer-input:disabled{opacity:.6;cursor:not-allowed}
.adp-chatpage{max-width:900px;height:calc(100dvh - 128px);min-height:560px;display:flex;flex-direction:column;margin:0 auto}
.adp-chat-head{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin:0 0 8px;flex:0 0 auto}
.adp-chat-title{min-width:0}
.adp-chat-head .adp-title{font-size:21px}
.adp-chat-head .adp-lede{max-width:100%}
.adp-chat-main{flex:1 1 auto;min-height:0;display:flex;flex-direction:column}
.adp-chat-scroll{flex:1 1 auto;min-height:0;overflow:auto;display:flex;flex-direction:column;gap:16px;padding:14px 2px 22px}
.adp-chat-scroll.empty{justify-content:center;align-items:center}
.adp-chat-empty{max-width:560px;margin:0 auto;text-align:center;display:flex;flex-direction:column;align-items:center;gap:9px;padding:24px 12px}
.adp-chat-empty-mark{width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;border:1px solid rgba(201,155,84,.4);color:#E2B96F;background:rgba(201,155,84,.08);font-size:18px;margin-bottom:3px}
.adp-chat-empty h2{font-size:19px;font-weight:700;letter-spacing:-.2px;margin:0}
.adp-chat-empty p{font-size:12px;line-height:1.65;color:var(--dsw-alias-label-secondary);margin:0}
.adp-chat-suggestions{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:10px}
.adp-suggestion{border:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-1);color:var(--dsw-alias-label-secondary);border-radius:999px;padding:7px 12px;font:inherit;font-size:11px;cursor:pointer;transition:border-color .15s ease,color .15s ease,background .15s ease}
.adp-suggestion:hover{border-color:#C99B54;color:var(--dsw-alias-label-primary);background:var(--dsw-alias-bg-layer-2)}
.adp-chatpage .adp-msg{border:0;background:transparent;padding:0;max-width:100%;font-size:13.5px;line-height:1.7;align-self:stretch}
.adp-chatpage .adp-msg.user{align-self:flex-end;max-width:min(78%,620px);background:var(--dsw-alias-bg-layer-2);border:1px solid var(--dsw-alias-border-l1);border-radius:18px 18px 6px 18px;padding:10px 14px}
.adp-chat-composer{flex:0 0 auto;padding:8px 0 2px;background:linear-gradient(180deg,transparent,var(--dsw-alias-bg-base) 18%)}
.adp-chat-composer .adp-composer{margin-top:0;border-radius:20px;box-shadow:0 8px 30px rgba(0,0,0,.16)}
.adp-chat-composer .adp-composer-input{display:block;width:100%;box-sizing:border-box;min-height:88px;max-height:220px;padding:16px 18px 8px;font-size:14px;line-height:1.65;border:0!important;outline:none!important;box-shadow:none!important;resize:none;-webkit-appearance:none}
.adp-chat-composer .adp-attachments{padding:0 14px 8px;align-items:flex-end}
.adp-chat-composer .adp-attach{width:78px;height:78px}
.adp-chat-composer .adp-attach-add{width:88px;height:78px;border-radius:10px;gap:3px}
.adp-chat-composer .adp-attach-add small{font-size:9px;color:var(--dsw-alias-label-secondary);white-space:nowrap}
.adp-chat-composer .adp-attach-add:hover small{color:#C99B54}
.adp-chat-composer .adp-composer-foot{padding:4px 10px 9px;background:transparent;border-top:0}
.adp-text-model{display:inline-flex;align-items:center;gap:6px;min-width:0;max-width:300px}
.adp-text-model>span{font:9px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.05em;color:#C99B54;white-space:nowrap}
.adp-text-model .adp-select{height:32px;max-width:240px;font-size:11px;min-width:140px}
.adp-composer-left{display:flex;align-items:center;gap:9px;min-width:0;flex:1 1 auto;flex-wrap:wrap}
.adp-composer-right{display:flex;align-items:center;gap:6px;flex:0 0 auto;margin-left:auto}
.adp-chat-composer .adp-composer{overflow:visible}
.adp-agent-icon{font-style:normal;flex:0 0 auto;width:22px;height:22px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;background:rgba(201,155,84,.12);color:#E2B96F;font-size:11px;line-height:1;border:1px solid rgba(201,155,84,.22)}
.adp-model-picker{position:relative;display:inline-flex;min-width:0;max-width:100%}
.adp-model-trigger{display:inline-flex;align-items:center;gap:6px;min-width:0;max-width:100%;border:0;background:transparent;color:var(--dsw-alias-label-secondary);border-radius:999px;padding:2px 5px 2px 2px;font:inherit;font-size:10.5px;cursor:pointer}
.adp-model-trigger:hover{background:var(--dsw-alias-bg-layer-2);color:var(--dsw-alias-label-primary)}
.adp-model-trigger:focus-visible{outline:1px solid #C99B54;outline-offset:1px}
.adp-model-name{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:240px;line-height:1.4}
.adp-model-caret{flex:0 0 auto;display:inline-flex;align-items:center;justify-content:center;width:14px;height:14px;opacity:.82;line-height:1}
.adp-model-menu{position:absolute;left:0;bottom:calc(100% + 7px);z-index:40;min-width:220px;max-width:min(320px,82vw);max-height:300px;overflow:auto;background:var(--dsw-alias-bg-layer-1);border:1px solid var(--dsw-alias-border-l2);border-radius:11px;box-shadow:0 14px 40px rgba(0,0,0,.28);padding:5px}
.adp-model-group+.adp-model-group{margin-top:4px;padding-top:4px;border-top:1px solid var(--dsw-alias-border-l1)}
.adp-model-group-label{padding:5px 8px 3px;color:var(--dsw-alias-label-secondary);font:9px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.07em;text-transform:uppercase;opacity:.75}
.adp-model-option{display:flex;align-items:center;justify-content:space-between;gap:12px;width:100%;border:0;background:transparent;color:var(--dsw-alias-label-primary);text-align:left;border-radius:7px;padding:7px 8px;font:inherit;font-size:11.5px;cursor:pointer;white-space:nowrap}
.adp-model-option:hover,.adp-model-option.on{background:var(--dsw-alias-bg-layer-2)}
.adp-model-option.on{color:#E2B96F}
.adp-model-left{display:flex;align-items:center;gap:6px;min-width:0;overflow:hidden}
.adp-model-right{display:flex;align-items:center;gap:6px;flex:none}
.adp-model-tag{font:9.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;padding:1px 5px;border-radius:999px;border:1px solid color-mix(in srgb,var(--dsw-alias-border-l1) 80%,transparent);color:var(--dsw-alias-label-secondary);white-space:nowrap}
.adp-model-off{font-size:9.5px;color:var(--dsw-alias-state-warn-primary);white-space:nowrap}
.adp-model-tags{display:flex;flex-wrap:wrap;gap:4px;margin:2px 0 3px}
.adp-chain{display:flex;flex-wrap:wrap;align-items:stretch;gap:6px;margin-top:8px}
.adp-chain-step{display:flex;align-items:center;gap:6px}
.adp-chain-node{display:flex;flex-direction:column;gap:2px;padding:6px 9px;border-radius:8px;border:1px solid color-mix(in srgb,var(--dsw-alias-border-l1) 85%,transparent);background:var(--dsw-alias-bg-layer-1)}
.adp-chain-node.on{border-color:color-mix(in srgb,var(--dsw-alias-state-success-primary) 45%,transparent)}
.adp-chain-node.off{opacity:.62}
.adp-chain-dot{width:6px;height:6px;border-radius:50%;background:var(--dsw-alias-label-faint,var(--dsw-alias-label-secondary))}
.adp-chain-node.on .adp-chain-dot{background:var(--dsw-alias-state-success-primary)}
.adp-chain-name{font-size:10.5px;font-weight:600}
.adp-chain-state{font-size:9.5px;color:var(--dsw-alias-label-secondary)}
.adp-chain-arrow{color:var(--dsw-alias-label-secondary);font-size:11px}
.adp-textmodel-row{align-items:center}
.adp-model-check{font-size:10px;color:#C99B54;flex:0 0 auto}
.adp-chat-composer .adp-composer-count{margin-left:auto;margin-right:9px;font-size:10px;color:var(--dsw-alias-label-secondary);opacity:.75}
.adp-send{flex:0 0 auto;width:34px;height:34px;border:0;border-radius:50%;background:var(--dsw-alias-label-primary);color:var(--dsw-alias-bg-base);font-size:17px;font-weight:700;line-height:1;cursor:pointer;display:inline-flex;align-items:center;justify-content:center}
.adp-send:hover{opacity:.88}
.adp-send:disabled{opacity:.35;cursor:not-allowed}
.adp-create-composer{margin-top:0}
.adp-preview-backdrop{position:fixed;inset:0;z-index:80;background:rgba(0,0,0,.76);display:flex;align-items:center;justify-content:center;padding:24px}
.adp-preview{max-width:92vw;max-height:92vh;display:flex;flex-direction:column;gap:8px;outline:none}
.adp-preview-head{display:flex;align-items:center;justify-content:space-between;gap:12px;color:#fff;font-size:11px}
.adp-preview-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;opacity:.82}
.adp-preview-img,.adp-preview-video{display:block;max-width:90vw;max-height:82vh;min-width:0;min-height:0;object-fit:contain;border-radius:10px;background:#000;box-shadow:0 18px 60px rgba(0,0,0,.45)}
.adp-msg{border:1px solid var(--dsw-alias-border-l1);border-radius:8px;padding:8px 9px;background:var(--dsw-alias-bg-layer-2);font-size:11.5px;white-space:pre-wrap}
.adp-msg.user{background:var(--dsw-alias-bg-overlay)}
.adp-change{border-left:2px solid #C99B54;padding:5px 8px;background:var(--dsw-alias-bg-layer-2);border-radius:0 6px 6px 0;font-size:10.5px}
.adp-crash{min-height:520px;display:flex;align-items:center;justify-content:center;padding:24px;background:var(--dsw-alias-bg-base)}
.adp-crash .box{max-width:640px;border:1px solid var(--dsw-alias-state-error-primary);border-radius:12px;padding:18px;background:var(--dsw-alias-bg-layer-1);color:var(--dsw-alias-label-primary);font-size:12px;line-height:1.55;white-space:pre-wrap}
.adp-crash h3{margin:0 0 8px;font-size:14px;color:var(--dsw-alias-state-error-primary)}
.adp-create-tabs{display:flex;align-items:center;gap:4px;margin:14px 0 0;border-bottom:1px solid var(--dsw-alias-border-l1)}
.adp-create-tab{position:relative;border:0;background:transparent;color:var(--dsw-alias-label-secondary);padding:8px 12px;cursor:pointer;font:inherit;font-size:12px}
.adp-create-tab:hover{color:var(--dsw-alias-label-primary)}
.adp-create-tab.on{color:var(--dsw-alias-label-primary);font-weight:650}
.adp-create-tab.on:after{content:"";position:absolute;left:10px;right:10px;bottom:-1px;height:2px;background:#C99B54;border-radius:2px 2px 0 0}
.adp-create-tab:disabled{opacity:.38;cursor:not-allowed}
.adp-create-tab-note{font:9px/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;color:#C99B54;margin-left:5px}
.adp-image-result{max-width:1120px;margin:0 auto;display:flex;flex-direction:column;gap:14px}
.adp-image-grid{display:grid;grid-template-columns:minmax(300px,1.1fr) minmax(280px,.9fr);gap:14px;align-items:start}
.adp-image-stage{min-height:420px;border:1px solid var(--dsw-alias-border-l1);border-radius:12px;background:radial-gradient(120% 100% at 50% 0%,#171a22 0%,#050608 70%);display:flex;align-items:center;justify-content:center;overflow:hidden;padding:12px}
.adp-image-stage img{max-width:100%;max-height:72vh;display:block;border-radius:7px;object-fit:contain}
.adp-image-prompt{font-size:11.5px;line-height:1.65;white-space:pre-wrap;overflow-wrap:anywhere;color:var(--dsw-alias-label-primary);max-height:240px;overflow:auto}
@media(max-width:900px){.adp-image-grid{grid-template-columns:1fr}.adp-image-stage{min-height:260px}}
.adp-composer{border:1px solid var(--dsw-alias-border-l1);border-radius:14px;background:var(--dsw-alias-bg-layer-1);overflow:hidden;margin-top:14px}
.adp-composer:focus-within{border-color:#C99B54;box-shadow:0 0 0 2px rgba(229,180,92,.12)}
.adp-composer-head{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:11px 15px;border-bottom:1px solid var(--dsw-alias-border-l1);font:10px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--dsw-alias-label-secondary)}
.adp-composer-label{color:var(--dsw-alias-label-primary);font-weight:600}
.adp-composer-count{font-variant-numeric:tabular-nums;opacity:.8}
.adp-composer-input{display:block;width:100%;min-height:150px;max-height:300px;resize:vertical;border:0;outline:0;background:transparent;color:var(--dsw-alias-label-primary);padding:14px 15px;font:13.5px/1.65 inherit;box-sizing:border-box}
.adp-composer-input::placeholder{color:var(--dsw-alias-label-secondary);opacity:.8}
.adp-attachments{display:flex;flex-wrap:wrap;gap:8px;padding:0 15px 12px}
.adp-attach{position:relative;width:68px;height:68px;border-radius:8px;overflow:hidden;border:1px solid var(--dsw-alias-border-l1);background:#0b0d12}
.adp-attach img,.adp-attach video{width:100%;height:100%;object-fit:cover;display:block}
.adp-attach-remove{position:absolute;top:3px;right:3px;width:17px;height:17px;border:0;border-radius:50%;background:rgba(0,0,0,.62);color:#fff;font-size:12px;line-height:17px;cursor:pointer}
.adp-attach-kind{position:absolute;left:4px;bottom:4px;border-radius:3px;padding:1px 4px;background:rgba(0,0,0,.62);color:#fff;font:8.5px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace}
.adp-attach-add{width:68px;height:68px;border:1px dashed var(--dsw-alias-border-l2);border-radius:8px;background:transparent;color:var(--dsw-alias-label-secondary);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;cursor:pointer;font:10px/1.2 inherit}
.adp-attach-add:hover{border-color:#C99B54;color:var(--dsw-alias-label-primary)}
.adp-attach-add b{font-size:18px;font-weight:300}
.adp-detected{display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:0 15px 10px;color:var(--dsw-alias-label-secondary);font-size:10px}
.adp-detected-chip{border:1px solid rgba(229,180,92,.35);border-radius:999px;padding:2px 7px;color:#C99B54;background:rgba(229,180,92,.06);font:10px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}
.adp-conflict{margin:0 15px 10px;padding:7px 9px;border:1px solid color-mix(in srgb,var(--dsw-alias-state-warn-primary) 45%,transparent);border-radius:7px;background:color-mix(in srgb,var(--dsw-alias-state-warn-primary) 8%,transparent);color:var(--dsw-alias-label-secondary);font-size:10.5px;line-height:1.45}
.adp-conflict b{color:var(--dsw-alias-state-warn-primary);font-weight:600;margin-right:6px}
.adp-composer-foot{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:10px 15px;border-top:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-2)}
.adp-model-select{height:32px;min-width:180px;max-width:260px;font-size:11px}
.adp-ref-upload{position:relative;display:inline-flex;align-items:center;justify-content:center;height:32px;padding:0 10px;border:1px dashed var(--dsw-alias-border-l2);border-radius:7px;color:var(--dsw-alias-label-secondary);font-size:11.5px;cursor:pointer;overflow:hidden;max-width:260px}
.adp-ref-upload:hover{border-color:#C99B54;color:var(--dsw-alias-label-primary)}
.adp-ref-upload.has{border-style:solid;padding:0 6px 0 4px}
.adp-ref-chip{display:inline-flex;align-items:center;gap:6px;min-width:0}
.adp-ref-chip img{width:24px;height:24px;border-radius:4px;object-fit:cover;flex:0 0 auto}
.adp-ref-name{max-width:170px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

.adp-advanced-panel{border:1px solid var(--dsw-alias-border-l1);border-radius:12px;background:var(--dsw-alias-bg-layer-1);padding:13px 15px;margin-top:10px}
.adp-settings-page .adp-section-head{margin-top:16px}
.adp-dsh-line{display:flex;align-items:center;justify-content:space-between;gap:10px;border:1px solid var(--dsw-alias-border-l1);border-radius:9px;background:var(--dsw-alias-bg-layer-1);padding:9px 11px}
.adp-provider-grid{display:flex;flex-direction:column;gap:11px;align-items:stretch}
.adp-provider-card{border:1px solid var(--dsw-alias-border-l1);border-radius:11px;background:var(--dsw-alias-bg-layer-1);padding:13px 14px;display:flex;flex-direction:column;gap:9px;min-width:0}
.adp-provider-card.configured{border-color:color-mix(in srgb,var(--dsw-alias-state-success-primary) 38%,var(--dsw-alias-border-l1))}
.adp-provider-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}
.adp-provider-name{font-size:13px;font-weight:700;margin-bottom:2px}
.adp-keyrow{display:flex;gap:6px;align-items:center}
.adp-keyrow .adp-input{height:30px;font-size:11px}
.adp-remote-line{display:flex;align-items:center;gap:7px;flex-wrap:wrap;border:1px solid color-mix(in srgb,var(--dsw-alias-state-success-primary) 28%,var(--dsw-alias-border-l1));border-radius:7px;padding:5px 7px;background:color-mix(in srgb,var(--dsw-alias-state-success-primary) 5%,transparent);font-size:10px;color:var(--dsw-alias-label-secondary);line-height:1.4}
.adp-remote-label{font:9px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.04em;color:var(--dsw-alias-state-success-primary);white-space:nowrap}
.adp-provider-models-title{font:9px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--dsw-alias-label-secondary);opacity:.8}
.adp-models-toggle{display:flex;align-items:center;gap:8px;width:100%;border:0;border-top:1px solid var(--dsw-alias-border-l1);background:transparent;color:var(--dsw-alias-label-primary);padding:9px 0 0;cursor:pointer;font:inherit;text-align:left}
.adp-models-toggle-title{font-size:11.5px;font-weight:650}
.adp-models-toggle-action{margin-left:auto;font:9.5px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;color:#C99B54;letter-spacing:.04em}
.adp-models-toggle:hover .adp-models-toggle-action{color:var(--dsw-alias-label-primary)}
.adp-model-summary{display:flex;flex-wrap:wrap;gap:5px}
.adp-model-summary-chip{border:1px solid var(--dsw-alias-border-l1);border-radius:999px;background:var(--dsw-alias-bg-layer-2);padding:3px 7px;font-size:10px;color:var(--dsw-alias-label-secondary)}
.adp-provider-models{display:flex;flex-direction:column;gap:5px;border-top:1px solid var(--dsw-alias-border-l1);padding-top:8px}
.adp-provider-model{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;padding:6px 0;border-bottom:1px solid color-mix(in srgb,var(--dsw-alias-border-l1) 55%,transparent)}
.adp-provider-model:last-child{border-bottom:0}
.adp-provider-model-name{font-size:11.5px;font-weight:600;margin-bottom:1px}
.adp-provider-model.off{opacity:.58}
.adp-model-enable{display:inline-flex;align-items:center;gap:4px;font-size:10px;color:var(--dsw-alias-label-secondary);cursor:pointer;white-space:nowrap}
.adp-model-enable input{accent-color:#C99B54;width:13px;height:13px;margin:0}
.adp-provider-model.on .adp-provider-model-name{color:var(--dsw-alias-label-primary)}
.adp-notice{border:1px solid color-mix(in srgb,var(--dsw-alias-state-success-primary) 42%,transparent);background:color-mix(in srgb,var(--dsw-alias-state-success-primary) 8%,transparent);border-radius:8px;padding:8px 10px;color:var(--dsw-alias-label-secondary);font-size:11px;margin-top:10px}
.adp-persona-inline{border:1px solid var(--dsw-alias-border-l1);border-radius:10px;background:var(--dsw-alias-bg-layer-2);padding:11px 12px;display:flex;flex-direction:column;gap:9px}
.adp-persona-off{opacity:.45;pointer-events:none;user-select:none}
.adp-persona-source{display:flex;flex-direction:column;gap:4px}
.adp-persona-source .adp-select{width:100%;height:31px}
.adp-persona-status{display:flex;align-items:flex-start;gap:8px;flex-wrap:wrap;line-height:1.45}
.adp-persona-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;border-top:1px solid var(--dsw-alias-border-l1);padding-top:9px}
.adp-persona-actions .adp-hint{margin:0}
.adp-persona-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}
.adp-empty-state{border:1px dashed var(--dsw-alias-border-l2);border-radius:12px;padding:20px;display:flex;flex-direction:column;align-items:flex-start;gap:7px;background:var(--dsw-alias-bg-layer-1)}
.adp-modal-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.56);z-index:90;display:flex;align-items:center;justify-content:center;padding:20px}
.adp-modal{width:min(720px,94vw);max-height:88vh;background:var(--dsw-alias-bg-layer-1);border:1px solid var(--dsw-alias-border-l1);border-radius:14px;box-shadow:0 24px 80px rgba(0,0,0,.45);display:flex;flex-direction:column;overflow:hidden;animation:adp-modal-in .16s ease-out}
@keyframes adp-modal-in{from{opacity:.5;transform:translateY(8px) scale(.99)}to{opacity:1;transform:none}}
.adp-modal-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:16px 18px;border-bottom:1px solid var(--dsw-alias-border-l1)}
.adp-modal-body{padding:16px 18px;overflow:auto;display:flex;flex-direction:column;gap:16px}
.adp-modal-section{display:flex;flex-direction:column;gap:9px}
.adp-modal-section-title{font:10px/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;color:#C99B54}
.adp-modal-foot{display:flex;justify-content:flex-end;gap:8px;padding:13px 18px;border-top:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-2)}
.adp-persona-modal{width:min(880px,94vw);max-height:90vh}
.adp-persona-modal .adp-modal-body{padding:20px 22px;gap:18px}
.adp-persona-modal .adp-modal-section{padding:14px 16px 16px;border:1px solid var(--dsw-alias-border-l1);border-radius:10px;background:var(--dsw-alias-bg-layer-2)}
.adp-persona-modal .adp-modal-section .adp-field-grid{gap:12px 14px}
.adp-persona-modal .adp-modal-section .adp-field-label{margin-bottom:6px}
.adp-persona-modal .adp-modal-section .adp-input,.adp-persona-modal .adp-modal-section .adp-select{height:35px;font-size:12.5px}
@media(max-width:620px){.adp-persona-modal{max-height:94vh;width:100%}.adp-persona-modal .adp-modal-body{padding:13px}.adp-persona-modal .adp-modal-section{padding:12px}.adp-persona-modal .adp-field-grid{grid-template-columns:1fr !important}}
.adp-personas{display:grid;grid-template-columns:minmax(250px,.72fr) minmax(0,1.28fr);gap:14px;align-items:start}
.adp-persona-list{display:flex;flex-direction:column;gap:8px;min-width:0}
.adp-persona-card{border:1px solid var(--dsw-alias-border-l1);border-radius:10px;background:var(--dsw-alias-bg-layer-1);padding:11px 12px;min-width:0}
.adp-persona-card.on{border-color:#C99B54;box-shadow:0 0 0 1px #C99B54 inset}
.adp-persona-card .adp-h2{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
@media(max-width:900px){.adp-personas{grid-template-columns:1fr}}
.adp-split{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(280px,.65fr);gap:14px}
.adp-slots{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.adp-slot{border:1px dashed var(--dsw-alias-border-l2);border-radius:9px;min-height:92px;display:flex;align-items:center;justify-content:center;cursor:pointer;background:var(--dsw-alias-bg-layer-2);overflow:hidden;position:relative}
.adp-slot img,.adp-slot video{width:100%;height:104px;object-fit:cover;display:block}
.adp-slot .fill{position:absolute;inset:0;display:flex;align-items:flex-end;justify-content:flex-start;padding:7px;background:linear-gradient(transparent 40%,rgba(0,0,0,.55));color:#fff;font-size:10px}
.adp-chips{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.adp-chip{border:1px solid var(--dsw-alias-border-l1);border-radius:999px;padding:3px 9px;font-size:10.5px;color:var(--dsw-alias-label-secondary);background:var(--dsw-alias-bg-layer-2)}
.adp-asset-foot{margin-top:14px;padding-top:12px;border-top:1px solid var(--dsw-alias-border-l1);color:var(--dsw-alias-label-secondary);font-size:10.5px;line-height:1.6}
.adp-asset-foot b{display:block;color:var(--dsw-alias-label-primary);font-size:10.5px;margin-bottom:4px;font-weight:600}
.adp-result{display:flex;flex-direction:column;gap:14px;max-width:1120px;margin:0 auto}
.adp-result-head{display:flex;align-items:center;gap:12px;min-height:38px}
.adp-back{display:inline-flex;align-items:center;gap:4px;border:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-2);color:var(--dsw-alias-label-secondary);border-radius:7px;padding:6px 9px;cursor:pointer;font:inherit;font-size:11.5px;white-space:nowrap}
.adp-back:hover{color:var(--dsw-alias-label-primary);border-color:#C99B54}
.adp-result-title{min-width:0;flex:1 1 auto}
.adp-result-badges{display:flex;align-items:center;gap:6px;flex:0 0 auto}
.adp-result-grid{display:grid;grid-template-columns:minmax(300px,380px) minmax(0,1fr);gap:14px;align-items:start}
.adp-stage{position:relative;height:420px;display:flex;align-items:center;justify-content:center;background:radial-gradient(120% 100% at 50% 0%,#171a22 0%,#050608 70%);border:1px solid var(--dsw-alias-border-l1);border-radius:12px;overflow:hidden}
.adp-stage-video{display:block;max-width:100%;max-height:100%;background:#000}
.adp-empty-stage{color:var(--dsw-alias-label-secondary);font-size:11px;text-align:center;padding:20px}
.adp-stage-progress{position:absolute;left:12px;right:12px;bottom:12px;padding:8px 9px;border-radius:7px;background:rgba(8,9,13,.82);backdrop-filter:blur(6px);display:flex;flex-direction:column;gap:5px;color:#fff;font-size:10px}
.adp-result-side{border:1px solid var(--dsw-alias-border-l1);border-radius:12px;background:var(--dsw-alias-bg-layer-1);overflow:hidden}
.adp-side-block{padding:13px 15px;border-bottom:1px solid var(--dsw-alias-border-l1)}
.adp-side-block:last-child{border-bottom:0}
.adp-side-label{font:10px/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--dsw-alias-label-secondary);margin-bottom:8px}
.adp-action-list{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}
.adp-action{display:flex;align-items:center;justify-content:flex-start;gap:6px;min-width:0;overflow:hidden;border:1px solid var(--dsw-alias-border-l1);border-radius:8px;padding:8px 9px;background:var(--dsw-alias-bg-layer-2);color:var(--dsw-alias-label-primary);cursor:pointer;font:inherit;font-size:11.5px;text-align:left;line-height:1.3}
.adp-action:hover{border-color:#C99B54;background:var(--dsw-alias-bg-layer-1)}
.adp-action:focus-visible,.adp-back:focus-visible,.adp-shot-edit:focus-visible,.adp-icon-btn:focus-visible{outline:2px solid #C99B54;outline-offset:2px}
.adp-action:disabled{opacity:.4;cursor:not-allowed}
.adp-action.danger{color:var(--dsw-alias-state-error-primary)}
.adp-action svg{flex:0 0 auto;color:#C99B54}
.adp-action span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.adp-action.danger svg{color:var(--dsw-alias-state-error-primary)}
.adp-side-note{font-size:10.5px;line-height:1.55;color:var(--dsw-alias-label-secondary);margin-top:8px}
.adp-facts{display:grid;grid-template-columns:1fr 1fr;gap:8px 12px}
.adp-fact{display:flex;flex-direction:column;gap:2px;min-width:0}
.adp-fact span{font:9.5px/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.04em;color:var(--dsw-alias-label-secondary);text-transform:uppercase}
.adp-fact b{font-size:11.5px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.adp-qa{display:flex;align-items:center;gap:8px}
.adp-qa-note{font-size:10.5px;color:var(--dsw-alias-label-secondary);margin-top:6px;line-height:1.45}
.adp-inputs{border:1px solid var(--dsw-alias-border-l1);border-radius:12px;background:var(--dsw-alias-bg-layer-1);overflow:hidden}
.adp-inputs-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 14px;border-bottom:1px solid var(--dsw-alias-border-l1)}
.adp-inputs-grid{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(260px,.9fr);gap:0}
.adp-input-brief{position:relative;padding:13px 14px;min-width:0;border-right:1px solid var(--dsw-alias-border-l1)}
.adp-input-label{font:10px/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--dsw-alias-label-secondary);margin-bottom:7px}
.adp-brief-text{font-size:12px;line-height:1.65;white-space:pre-wrap;overflow-wrap:anywhere;color:var(--dsw-alias-label-primary)}
.adp-copy{position:absolute;right:12px;top:10px;display:inline-flex;align-items:center;gap:4px;border:1px solid var(--dsw-alias-border-l1);border-radius:6px;background:var(--dsw-alias-bg-layer-2);color:var(--dsw-alias-label-secondary);padding:3px 6px;font:inherit;font-size:10px;cursor:pointer}
.adp-copy:hover{color:var(--dsw-alias-label-primary);border-color:#C99B54}
.adp-copy svg{color:#C99B54}
.adp-input-assets{display:flex;flex-direction:column;gap:9px;padding:13px 14px;min-width:0}
.adp-asset-line{display:flex;align-items:center;gap:8px;min-width:0}
.adp-asset-tag{font:9.5px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.03em;color:#C99B54;white-space:nowrap;flex:0 0 auto}
.adp-asset-name{font-size:11px;color:var(--dsw-alias-label-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.adp-asset-thumbs{display:flex;gap:4px;flex-wrap:wrap}
.adp-asset-thumb{width:26px;height:26px;border-radius:4px;overflow:hidden;border:1px solid var(--dsw-alias-border-l1);background:#0a0b10;display:inline-block}
.adp-asset-thumb img{width:100%;height:100%;object-fit:cover;display:block}
.adp-storyboard{border:1px solid var(--dsw-alias-border-l1);border-radius:12px;background:var(--dsw-alias-bg-layer-1);overflow:hidden}
.adp-storyboard-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 14px;border-bottom:1px solid var(--dsw-alias-border-l1)}
.adp-storyboard-meta{font-size:10.5px;color:var(--dsw-alias-label-secondary)}
.adp-shot{display:grid;grid-template-columns:72px minmax(0,1fr) auto;gap:12px;align-items:start;padding:11px 14px;border-bottom:1px solid var(--dsw-alias-border-l1)}
.adp-shot:last-child{border-bottom:0}
.adp-shot.open{background:var(--dsw-alias-bg-layer-2)}
.adp-shot-thumb{position:relative;width:72px;height:96px;border-radius:7px;overflow:hidden;background:#0a0b10;border:1px solid var(--dsw-alias-border-l1);flex:0 0 auto}
.adp-shot-thumb img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block}
.adp-shot-placeholder{position:absolute;inset:0;background:linear-gradient(135deg,#1a1d26,#0b0d12)}
.adp-shot-loading{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;gap:6px;background:rgba(10,11,16,.78);color:var(--dsw-alias-label-secondary);font-size:10px;letter-spacing:.02em}
.adp-shot-loading::before{content:'';width:11px;height:11px;border-radius:50%;border:2px solid rgba(255,255,255,.22);border-top-color:#fff;animation:adp-spin .8s linear infinite}
@keyframes adp-spin{to{transform:rotate(360deg)}}
.adp-shot-index{position:absolute;left:4px;bottom:4px;border-radius:4px;padding:1px 4px;background:rgba(8,9,13,.72);color:#fff;font:9px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace}
.adp-shot-body{min-width:0;padding-top:1px}
.adp-shot-top{display:flex;align-items:baseline;gap:8px;min-width:0}
.adp-shot-top b{font-size:12.5px;font-weight:700}
.adp-shot-time{font:9.5px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--dsw-alias-label-secondary);white-space:nowrap}
.adp-shot-dialogue{font-size:12px;line-height:1.5;margin-top:5px;color:var(--dsw-alias-label-primary);overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.adp-shot-lines{font-size:12px;line-height:1.5;margin-top:5px;color:var(--dsw-alias-label-primary);overflow-wrap:anywhere}
.adp-shot-lines div+div{margin-top:1px}
.adp-line-at{font:9.5px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--dsw-alias-label-secondary)}
.adp-shot-action{font-size:10.5px;line-height:1.45;color:var(--dsw-alias-label-secondary);margin-top:3px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.adp-shot-edit{display:inline-flex;align-items:center;gap:4px;border:1px solid var(--dsw-alias-border-l1);border-radius:6px;background:transparent;color:var(--dsw-alias-label-secondary);padding:4px 7px;font:inherit;font-size:10.5px;cursor:pointer;white-space:nowrap;margin-top:2px}
.adp-shot-edit:hover{color:var(--dsw-alias-label-primary);border-color:#C99B54}
.adp-shot-edit svg{color:#C99B54}
.adp-shot-editor{grid-column:1/-1;display:flex;flex-direction:column;gap:8px;border-top:1px solid var(--dsw-alias-border-l1);padding-top:10px;margin-top:1px}
.adp-shot-editor-head{font:10px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.05em;text-transform:uppercase;color:#C99B54}
.adp-shot-chat-row .adp-input{height:32px}
.adp-empty-shots{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:16px 14px;color:var(--dsw-alias-label-secondary);font-size:11px}
.adp-result-error{border:1px solid color-mix(in srgb,var(--dsw-alias-state-error-primary) 45%,transparent);border-radius:8px;padding:9px 11px;background:color-mix(in srgb,var(--dsw-alias-state-error-primary) 8%,transparent)}
.adp-drawer-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.52);z-index:80;display:flex;justify-content:flex-end}
.adp-drawer{width:min(380px,92vw);height:100%;background:var(--dsw-alias-bg-layer-1);border-left:1px solid var(--dsw-alias-border-l1);box-shadow:-18px 0 50px rgba(0,0,0,.35);display:flex;flex-direction:column;animation:adp-slide-in .18s ease-out}
@keyframes adp-slide-in{from{transform:translateX(18px);opacity:.6}to{transform:translateX(0);opacity:1}}
.adp-drawer-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:16px;border-bottom:1px solid var(--dsw-alias-border-l1)}
.adp-drawer-body{display:flex;flex-direction:column;gap:14px;padding:16px;overflow:auto}
.adp-drawer-body .adp-select{width:100%;height:34px}
.adp-drawer-foot{margin-top:auto;display:flex;justify-content:flex-end;gap:8px;padding:14px 16px;border-top:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-2)}
.adp-icon-btn{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border:0;border-radius:50%;background:transparent;color:var(--dsw-alias-label-secondary);cursor:pointer;transition:background .15s ease,color .15s ease,transform .15s ease}
.adp-icon-btn:hover{color:#E2B96F;background:rgba(201,155,84,.12);transform:translateY(-1px)}
@media(hover:none){.adp-media .adp-remove{opacity:1}}
@media(max-width:980px){.adp-tab{padding:0 9px}.adp-panel-grid{grid-template-columns:1fr}.adp-asset-col{border-right:0;border-bottom:1px solid var(--dsw-alias-border-l1)}.adp-title{font-size:21px}}
@media(max-width:980px){.adp-result-grid{grid-template-columns:1fr}.adp-stage{height:360px;max-width:420px;margin:0 auto;width:100%}}
@media(max-width:760px){.adp-inputs-grid{grid-template-columns:1fr}.adp-input-brief{border-right:0;border-bottom:1px solid var(--dsw-alias-border-l1)}}
.adp-select,.adp-field .adp-select,.adp-toolbar .adp-select,.adp-persona-modal .adp-modal-section .adp-select{appearance:none;-webkit-appearance:none;background-image:linear-gradient(45deg,transparent 50%,#A8ABB4 50%),linear-gradient(135deg,#A8ABB4 50%,transparent 50%);background-repeat:no-repeat;background-position:calc(100% - 14px) 50%,calc(100% - 9px) 50%;background-size:5px 5px;padding-right:28px}
.adp-date-input{width:124px;flex:0 0 auto}
.adp-upload-label{position:relative;overflow:hidden;cursor:pointer;display:inline-flex;align-items:center;justify-content:center}
@media(max-width:620px){.adp-chatpage{height:auto;min-height:calc(100dvh - 150px)}.adp-chat-head{display:block}.adp-chat-actions{margin-top:8px}.adp-composer-left{flex:1 1 100%}.adp-composer-right{width:100%;justify-content:flex-end}.adp-model-picker{max-width:100%}.adp-model-trigger{max-width:100%}.adp-model-menu{min-width:min(280px,86vw)}.adp-chatpage .adp-msg.user{max-width:88%}.adp-preview-backdrop{padding:8px}.adp-preview-img,.adp-preview-video{max-width:94vw;max-height:80vh}.adp-modal-backdrop{padding:8px}.adp-modal{max-height:94vh;width:100%}.adp-modal-body{padding:13px}.adp-modal-foot{padding:12px}.adp-persona-grid{grid-template-columns:1fr}.adp-composer-input{min-height:120px;font-size:13px}.adp-composer-foot{align-items:stretch}.adp-composer-foot .adp-primary{width:100%;justify-content:center}.adp-model-select{min-width:0;flex:1 1 auto}
.adp-top{gap:8px;padding:0 12px}.adp-tabs{margin-left:0}.adp-tab{padding:0 8px}.adp-body{padding:16px 12px 32px}.adp-page-head{display:block}.adp-page-meta{margin-top:8px}.adp-field-grid.g3,.adp-field-grid.g4{grid-template-columns:repeat(2,minmax(0,1fr))}.adp-actionbar{margin-left:-14px;margin-right:-14px;padding:12px 14px}.adp-form-col{padding:16px 14px 0}.adp-asset-col{padding:14px}.adp-slots{grid-template-columns:1fr 1fr}.adp-result-head{flex-wrap:wrap}.adp-result-badges{width:100%;justify-content:flex-start}.adp-stage{height:320px}.adp-shot{grid-template-columns:56px minmax(0,1fr) auto;gap:9px;padding:10px}.adp-shot-thumb{width:56px;height:76px}.adp-shot-edit span{display:none}.adp-facts{grid-template-columns:1fr 1fr}}

.adp-setup{max-width:760px;margin:0 auto}
.adp-setup-hero{margin:6px 0 18px}
.adp-setup-item{display:grid;grid-template-columns:24px minmax(0,1fr) auto;gap:12px;align-items:start;padding:14px 16px;border:1px solid var(--dsw-alias-border-l1);border-radius:12px;background:var(--dsw-alias-bg-layer-1);margin-bottom:8px}
.adp-setup-item.bad{border-color:rgba(208,90,90,.45)}
.adp-setup-item.warn{border-color:rgba(229,180,92,.35)}
.adp-setup-ico{width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;background:var(--dsw-alias-bg-layer-2);color:var(--dsw-alias-label-secondary)}
.adp-setup-item.ok .adp-setup-ico{background:rgba(60,170,110,.16);color:#3caa6e}
.adp-setup-item.bad .adp-setup-ico{background:rgba(208,90,90,.15);color:#d05a5a}
.adp-setup-item.warn .adp-setup-ico{background:rgba(229,180,92,.15);color:#C99B54}
.adp-setup-title{font-weight:650;font-size:13px;line-height:1.4}
.adp-setup-detail{font-size:11px;color:var(--dsw-alias-label-secondary);word-break:break-all;margin-top:3px;line-height:1.5}
.adp-setup-fix{grid-column:2 / -1;margin-top:9px;display:flex;flex-direction:column;gap:7px}
.adp-setup-cmd{display:flex;align-items:center;gap:7px}
.adp-setup-cmd code{flex:1 1 auto;min-width:0;overflow:auto;white-space:nowrap;font:11px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--dsw-alias-bg-layer-2);border:1px solid var(--dsw-alias-border-l1);border-radius:7px;padding:7px 9px}
.adp-setup-note{font-size:10.5px;color:var(--dsw-alias-label-secondary);line-height:1.6}
.adp-setup-foot{display:flex;align-items:center;gap:9px;margin-top:18px;flex-wrap:wrap}
.adp-setup-group{font:10px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.1em;text-transform:uppercase;color:#C99B54;margin:18px 0 7px}
`
    /** Supervisor state, available even while the engine is still being prepared. */
    async function hostStatus() {
      try {
        const res = await fetch('/adplus/health', { headers: TOKEN ? { 'x-adplus-token': TOKEN } : {} })
        if (!res.ok) return null
        const data = await res.json()
        return data.engine || null
      } catch { return null }
    }

    async function restartEngineHost() {
      const res = await fetch('/adplus/api/engine/restart', { method: 'POST', headers: TOKEN ? { 'x-adplus-token': TOKEN } : {} })
      return res.ok
    }

    async function api(path, options) {
      await tokenReady()
      const opts = Object.assign({}, options || {})
      const headers = Object.assign({ 'x-adplus-token': TOKEN }, opts.headers || {})
      if (opts.body && typeof opts.body !== 'string' && !(opts.body instanceof Blob)) {
        headers['content-type'] = 'application/json'
        opts.body = JSON.stringify(opts.body)
      }
      const res = await fetch(API + path, Object.assign({}, opts, { headers }))
      const text = await res.text()
      let data = {}
      try { data = text ? JSON.parse(text) : {} } catch { data = { raw: text } }
      if (!res.ok) {
        const message = (data.error && (data.error.message || data.error.code)) || data.detail || ('HTTP ' + res.status)
        throw new Error(typeof message === 'string' ? message : JSON.stringify(message))
      }
      return data
    }

    /** Connection loss during an engine restart is not a user-facing failure. */
    function isTransientNetworkError(error) {
      const text = String((error && error.message) || error || '')
      return /ECONNRESET|ECONNREFUSED|EPIPE|ETIMEDOUT|socket hang up|fetch failed|network error|引擎正在重启/i.test(text)
    }

    function mediaUrl(path) {
      if (!path) return ''
      return MEDIA + '?path=' + encodeURIComponent(path) + '&token=' + encodeURIComponent(TOKEN)
    }

    function mediaUrlVersion(path, version) {
      const url = mediaUrl(path)
      if (!url) return ''
      return url + (url.includes('?') ? '&' : '?') + 'v=' + encodeURIComponent(version || 1)
    }

    async function uploadFile(file, kind) {
      await tokenReady()
      const res = await fetch(API + '/assets/upload?kind=' + encodeURIComponent(kind) + '&name=' + encodeURIComponent(file.name || 'upload'), {
        method: 'POST',
        headers: { 'content-type': file.type || 'application/octet-stream', 'x-adplus-token': TOKEN },
        body: file,
      })
      const data = await res.json()
      if (!res.ok) throw new Error((data.error && data.error.message) || data.detail || '上传失败')
      return Object.assign({}, data.asset, { deduplicated: Boolean(data.deduplicated) })
    }

    function fmt(seconds) {
      const s = Number(seconds || 0)
      if (!s) return '—'
      return s < 60 ? s.toFixed(1) + 's' : Math.floor(s / 60) + 'm' + Math.round(s % 60) + 's'
    }

    function fmtAt(seconds) {
      return Number(seconds || 0).toFixed(1) + 's'
    }



    function fmtDateTime(value) {
      if (!value) return '—'
      const date = new Date(value)
      if (Number.isNaN(date.getTime())) return String(value)
      return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
    }

    function fmtAssetDate(value) {
      if (!value) return '—'
      const date = new Date(value)
      if (Number.isNaN(date.getTime())) return String(value)
      const pad = (n) => String(n).padStart(2, '0')
      return date.getFullYear() + '/' + pad(date.getMonth() + 1) + '/' + pad(date.getDate()) + ' ' + pad(date.getHours()) + ':' + pad(date.getMinutes())
    }

    function runDuration(run) {
      if (!run || !run.created_at) return '—'
      const start = new Date(run.created_at).getTime()
      const end = run.finished_at ? new Date(run.finished_at).getTime() : Date.now()
      if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return '—'
      const seconds = Math.round((end - start) / 1000)
      return seconds < 60 ? seconds + 's' : Math.floor(seconds / 60) + 'm' + (seconds % 60) + 's'
    }

    async function downloadPost(path, body, filename) {
      await tokenReady()
      const res = await fetch(API + path, { method: 'POST', headers: { 'content-type': 'application/json', 'x-adplus-token': TOKEN }, body: JSON.stringify(body || {}) })
      if (!res.ok) {
        const text = await res.text()
        let message = '导出失败'
        try { const data = JSON.parse(text); message = data.detail || (data.error && data.error.message) || message } catch { /* noop */ }
        throw new Error(message)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename || 'adplus-export.zip'
      a.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    }

    function detectVideoParams(text) {
      const source = String(text || '')
      const aspect = (source.match(/(21:9|16:9|9:16|4:3|3:4|1:1)/) || [])[1] || (/竖屏/.test(source) ? '9:16' : /横屏/.test(source) ? '16:9' : /方屏|方形/.test(source) ? '1:1' : '')
      const duration = Number((source.match(/(\d{1,2})\s*(?:秒|s|sec)(?!\w)/i) || [])[1] || 0)
      const resolution = (source.match(/(1080p|720p|480p|2k)/i) || [])[1] || ''
      const mode = /(精细|分段|分镜)/.test(source) ? 'fine' : ''
      // Subtitles are a sidecar SRT switch. Judge the "off" phrasings first so
      // "不要字幕" never reads as "字幕".
      let subtitle = ''
      if (/字幕/.test(source)) {
        if (/(不要|不启用|不用|去掉|关闭|关掉|取消|别加|无)字幕|字幕(不要|关掉|关闭|去掉|不用)/.test(source)) subtitle = 'off'
        else if (/(加|开|要|带|生成|启用)字幕|字幕(打开|开启)/.test(source)) subtitle = 'sidecar'
      }
      const vendor = /可灵|kling/i.test(source) ? 'kling'
        : /seedance|方舟|ark/i.test(source) ? 'ark'
          : /minimax|海螺|hailuo/i.test(source) ? 'minimax' : ''
      return { aspect, duration: duration || 0, resolution: resolution ? resolution.toLowerCase().replace('2k', '1080p') : '', mode, subtitle, vendor }
    }

    /** First usable model from a vendor named in the brief, or '' when none. */
    function modelForVendor(vendor, models) {
      if (!vendor) return ''
      const row = (models || []).find((m) => m.kind === 'video' && m.provider === vendor && m.available && m.enabled !== false)
      return row ? row.id : ''
    }

    /** Default video model: first usable one, dialogue-capable first for remakes. */
    function defaultModelId(models, needsDialogue) {
      const rows = (models || []).filter((m) => m.kind === 'video' && m.available && m.enabled !== false && (m.capabilities || []).includes('text_to_video'))
      const real = rows.filter((m) => m.provider !== 'synthetic')
      const pool = real.length ? real : rows
      const withAudio = needsDialogue ? pool.filter((m) => m.native_audio) : pool
      const pick = (withAudio.length ? withAudio : pool)[0]
      return pick ? pick.id : ''
    }

    /** How the subtitle setting reads in the UI. */
    function subtitleLabel(value) {
      return value === 'sidecar' ? 'SRT 旁挂' : '不启用'
    }

    async function parseIntentWithDsh(brief) {
      try {
        const data = await api('/dsh/chat', { method: 'POST', body: {
          system: '你是广告视频参数解析器。只输出 JSON，不要解释，不要 markdown。字段：aspect（9:16|16:9|1:1|4:3|3:4|21:9 或 null）、duration（整数秒或 null）、resolution（480p|720p|1080p 或 null）、generation_mode（fast|fine 或 null）、subtitle（off|sidecar|null，是否交付 SRT 旁挂字幕）、model_vendor（kling|ark|minimax|null，用户点名的厂商）、reason（一句话）。只按用户明确表达解析，不要猜。',
          messages: [{ role: 'user', content: [{ type: 'text', text: String(brief || '').slice(0, 1000) }] }],
          maxTokens: 500,
        } })
        const text = String((data.dsh && data.dsh.text) || '')
        const start = text.indexOf('{')
        const end = text.lastIndexOf('}')
        if (start < 0 || end <= start) return null
        const value = JSON.parse(text.slice(start, end + 1))
        const aspects = ['9:16', '16:9', '1:1', '4:3', '3:4', '21:9']
        const resolutions = ['480p', '720p', '1080p']
        const duration = Number(value.duration)
        const vendors = ['kling', 'ark', 'minimax']
        return {
          aspect: aspects.includes(value.aspect) ? value.aspect : '',
          duration: Number.isFinite(duration) && duration >= 1 && duration <= 30 ? duration : 0,
          resolution: resolutions.includes(String(value.resolution || '').toLowerCase()) ? String(value.resolution).toLowerCase() : '',
          mode: value.generation_mode === 'fine' ? 'fine' : '',
          subtitle: ['off', 'sidecar'].includes(value.subtitle) ? value.subtitle : '',
          vendor: vendors.includes(String(value.model_vendor || '')) ? String(value.model_vendor) : '',
        }
      } catch (e) { return null }
    }

    function Badge({ status, children }) {
      return h('span', { className: 'adp-badge ' + (status || '') }, children)
    }

    const CAPABILITY_LABELS = {
      text_to_video: '文生视频', image_to_video: '图生视频', reference_to_video: '参考视频',
      text_to_image: '文生图', image_to_image: '图生图',
    }

    /** One small chip per declared capability. */
    function CapabilityChip({ capability }) {
      return h('span', { className: 'adp-cap' }, CAPABILITY_LABELS[capability] || capability)
    }

    function CapabilityChips({ row }) {
      const caps = (row && row.capabilities) || []
      return h('span', { className: 'adp-caps' }, caps.map((cap) => h(CapabilityChip, { key: cap, capability: cap })))
    }

    /** Short label for the supervisor's bootstrap stage. */
    function engineStageLabel(engine) {
      const stage = engine && engine.boot && engine.boot.stage
      if (stage === 'preparing') return '准备中'
      if (stage === 'failed') return '不可用'
      if (stage === 'stopped') return '已停止'
      if (stage === 'disabled') return '已关闭'
      return '离线'
    }

    function Icon(props) {
      const size = props.size || 18
      return h('svg', { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', 'aria-hidden': true },
        h('rect', { x: 3, y: 4, width: 18, height: 16, rx: 3, stroke: 'currentColor', strokeWidth: 1.8 }),
        h('path', { d: 'M10 9.2v5.6l4.8-2.8L10 9.2Z', fill: 'currentColor' }),
        h('path', { d: 'M3 16.5l4.2-3.2 3.1 2.4 3-2.2 4.7 3.3', stroke: 'currentColor', strokeWidth: 1.4, strokeLinecap: 'round' })
      )
    }

    function Glyph({ name, size = 14 }) {
      const paths = {
        back: 'M15 18l-6-6 6-6',
        edit: 'M4 20h4l11-11a2.8 2.8 0 0 0-4-4L4 16v4Z M13.5 6.5l4 4',
        refresh: 'M20 11a8 8 0 0 0-14-5 M4 4v6h6 M4 13a8 8 0 0 0 14 5 M20 20v-6h-6',
        download: 'M12 3v12 M8 11l4 4 4-4 M4 21h16',
        close: 'M6 6l12 12 M18 6L6 18',
        check: 'M4 12.5l5 5L20 6.5',
        play: 'M8 5l11 7-11 7V5Z',
        spark: 'M12 3l1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3Z',
        copy: 'M8 8h11v11H8V8Z M16 8V5H5v11h3',
        folder: 'M3 7a2 2 0 0 1 2-2h5l2 2h7v10H3V7Z',
        undo: 'M9 7H4v5 M4 12a8 8 0 1 0 2-5',
        plus: 'M12 5v14 M5 12h14',
        history: 'M12 4.4a7.6 7.6 0 1 1 0 15.2a7.6 7.6 0 1 1 0-15.2 M12 8.2V12l3 1.8',
      }
      return h('svg', { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true },
        h('path', { d: paths[name] || paths.spark })
      )
    }

    const DSH_MEDIA_MODEL = /(veo|seedance|happyhorse|gpt-image|nano-banana|(^|[-_.])wan(?:\d|[-_.])|image|video|t2v)/i

    function UploadSlot({ label, asset, kind, onAsset }) {
      const ref = useRef(null)
      const [busy, setBusy] = useState(false)
      const [err, setErr] = useState('')
      const choose = () => ref.current && ref.current.click()
      const onFile = async (event) => {
        const file = event.currentTarget.files && event.currentTarget.files[0]
        event.currentTarget.value = ''
        if (!file) return
        setBusy(true); setErr('')
        try { onAsset(await uploadFile(file, kind)) } catch (e) { setErr(String(e.message || e)) } finally { setBusy(false) }
      }
      return h('div', { className: 'adp-col' },
        h('div', { className: 'adp-small adp-muted' }, label),
        h('div', { className: 'adp-slot', onClick: busy ? undefined : choose, title: asset ? '点击替换' : '点击上传' },
          busy ? h('span', { className: 'adp-small adp-muted' }, '上传中…') : (
            asset ? (asset.kind === 'image'
              ? h('img', { src: mediaUrl(asset.path), alt: asset.name })
              : h('video', { src: mediaUrl(asset.path), muted: true, playsInline: true }))
              : h('span', { className: 'adp-small adp-muted' }, '＋ ' + label)
          ),
          asset ? h('div', { className: 'fill' }, asset.name) : null
        ),
        err ? h('div', { className: 'adp-error' }, err) : null,
        h('input', { ref, type: 'file', accept: kind === 'video' ? 'video/*' : 'image/*', onChange: onFile, style: { display: 'none' } })
      )
    }

    function Select({ value, onChange, options, label }) {
      return h('label', { className: 'adp-chip' },
        label ? h('span', { className: 'adp-muted' }, label + ' ') : null,
        h('select', { className: 'adp-select', value, onChange: (e) => onChange(e.currentTarget.value), style: { border: 0, background: 'transparent', padding: 0 } },
          (options || []).map((opt) => h('option', { key: String(opt.value ?? opt), value: String(opt.value ?? opt) }, opt.label ?? String(opt)))
        )
      )
    }

    function Field({ label, hint, children, style }) {
      return h('div', { className: 'adp-field', style },
        label ? h('div', { className: 'adp-field-label' }, label) : null,
        children,
        hint ? h('div', { className: 'adp-hint' }, hint) : null
      )
    }

    function FormSelect({ label, value, onChange, options }) {
      return h(Field, { label },
        h('select', { className: 'adp-select', value, onChange: (e) => onChange(e.currentTarget.value) },
          (options || []).map((opt) => h('option', { key: String(opt.value ?? opt), value: String(opt.value ?? opt) }, opt.label ?? String(opt)))
        )
      )
    }

    /** DSH catalogue plus the engine's Doubao-Seed-2.1 rows (tags kept). */
    function dshTextModels(dsh, textModels) {
      const rows = []
      if (dsh && dsh.available) {
        for (const provider of dsh.providers || []) {
          for (const model of provider.models || []) {
            rows.push({ provider: provider.id, providerName: provider.name || provider.id, model: model.id, name: model.name || model.id, tags: [], status: '' })
          }
        }
      }
      for (const model of textModels || []) {
        rows.push({
          provider: model.provider || 'ark',
          providerName: model.provider === 'ark' ? '火山方舟' : (model.provider || ''),
          model: model.id,
          name: model.label || model.id,
          tags: model.tags || [],
          status: model.status || '',
        })
      }
      return rows
    }

    function defaultDshTextModel(dsh, textModels) {
      const rows = dshTextModels(dsh, textModels)
      if (!rows.length) return null
      const selected = dsh && dsh.selection
      if (selected && rows.some((row) => row.provider === selected.provider && row.model === selected.model)) {
        return { provider: selected.provider, model: selected.model }
      }
      return { provider: rows[0].provider, model: rows[0].model }
    }

    function textModelKey(value) {
      return value && value.provider && value.model ? value.provider + '|' + value.model : ''
    }

    function TextModelSelect({ dsh, textModels, value, onChange }) {
      const rows = dshTextModels(dsh, textModels)
      const [open, setOpen] = useState(false)
      const rootRef = useRef(null)
      useEffect(() => {
        if (!open) return
        const onDown = (event) => { if (rootRef.current && !rootRef.current.contains(event.target)) setOpen(false) }
        const onKey = (event) => { if (event.key === 'Escape') setOpen(false) }
        document.addEventListener('mousedown', onDown)
        document.addEventListener('keydown', onKey)
        return () => {
          document.removeEventListener('mousedown', onDown)
          document.removeEventListener('keydown', onKey)
        }
      }, [open])
      if (!rows.length) return null
      const fallback = defaultDshTextModel(dsh, textModels)
      const selected = value && rows.some((row) => row.provider === value.provider && row.model === value.model) ? value : fallback
      const selectedRow = rows.find((row) => row.provider === selected.provider && row.model === selected.model) || rows[0]
      const groups = new Map()
      for (const row of rows) {
        if (!groups.has(row.provider)) groups.set(row.provider, { name: row.providerName, rows: [] })
        groups.get(row.provider).rows.push(row)
      }
      return h('div', { className: 'adp-model-picker', ref: rootRef },
        h('button', {
          type: 'button',
          className: 'adp-model-trigger',
          title: '选择对话模型',
          'aria-haspopup': 'listbox',
          'aria-expanded': open,
          onClick: () => setOpen((prev) => !prev),
        },
          h('i', { className: 'adp-agent-icon', 'aria-hidden': 'true', title: '智能体' }, '✦'),
          h('span', { className: 'adp-model-name' }, selectedRow.name),
          h('span', { className: 'adp-model-caret', 'aria-hidden': 'true' },
            h('svg', { width: 12, height: 12, viewBox: '0 0 12 12' },
              h('path', { d: 'M3 4.5 6 7.5 9 4.5', fill: 'none', stroke: 'currentColor', strokeWidth: 1.5, strokeLinecap: 'round', strokeLinejoin: 'round' })
            )
          )
        ),
        open ? h('div', { className: 'adp-model-menu', role: 'listbox' },
          Array.from(groups.entries()).map(([provider, group]) => h('div', { key: provider, className: 'adp-model-group' },
            h('div', { className: 'adp-model-group-label' }, group.name),
            group.rows.map((row) => h('button', {
              key: row.model,
              type: 'button',
              role: 'option',
              'aria-selected': row.provider === selected.provider && row.model === selected.model,
              className: 'adp-model-option' + (row.provider === selected.provider && row.model === selected.model ? ' on' : ''),
              onClick: () => { onChange({ provider: row.provider, model: row.model }); setOpen(false) },
            },
              h('span', { className: 'adp-model-left' },
                h('span', { className: 'adp-model-label' }, row.name),
                (row.tags || []).map((tag) => h('span', { key: tag, className: 'adp-model-tag' }, tag))
              ),
              h('span', { className: 'adp-model-right' },
                row.status === 'not_open' ? h('span', { className: 'adp-model-off' }, '未开通') : null,
                row.provider === selected.provider && row.model === selected.model ? h('span', { className: 'adp-model-check' }, '✓') : null
              )
            ))
          ))
        ) : null
      )
    }

    function PreviewModal({ asset, onClose }) {
      useEffect(() => {
        const onKey = (e) => { if (e.key === 'Escape') onClose() }
        window.addEventListener('keydown', onKey)
        return () => window.removeEventListener('keydown', onKey)
      }, [onClose])
      if (!asset) return null
      const video = asset.kind === 'video' || /\.(mp4|mov|webm|m4v)$/i.test(String(asset.path || ''))
      return h('div', { className: 'adp-preview-backdrop', onClick: onClose },
        h('div', { className: 'adp-preview', role: 'dialog', 'aria-modal': 'true', 'aria-label': '素材预览', onClick: (e) => e.stopPropagation() },
          h('div', { className: 'adp-preview-head' },
            h('span', { className: 'adp-preview-name', title: asset.name || '' }, asset.name || '素材预览'),
            h('button', { className: 'adp-icon-btn', onClick: onClose, title: '关闭预览' }, '×')
          ),
          video
            ? h('video', { className: 'adp-preview-video', src: mediaUrl(asset.path), controls: true, autoPlay: true, playsInline: true })
            : h('img', { className: 'adp-preview-img', src: mediaUrl(asset.path), alt: asset.name || '素材预览' })
        )
      )
    }

    function DropVideo({ asset, onAsset, onPreview }) {
      const input = useRef(null)
      const [busy, setBusy] = useState(false)
      const [drag, setDrag] = useState(false)
      const [err, setErr] = useState('')
      const choose = () => { if (!busy) input.current && input.current.click() }
      const open = () => { if (asset && onPreview) onPreview(asset); else choose() }
      const take = async (file) => {
        if (!file) return
        setBusy(true); setErr('')
        try { onAsset(await uploadFile(file, 'video')) } catch (e) { setErr(String(e.message || e)) } finally { setBusy(false) }
      }
      return h('div', { className: 'adp-col' },
        h('div', {
          className: 'adp-drop' + (drag ? ' drag' : '') + (asset ? ' has-preview' : ''),
          onClick: open,
          role: 'button',
          tabIndex: 0,
          onKeyDown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open() } },
          onDragOver: (e) => { e.preventDefault(); setDrag(true) },
          onDragLeave: () => setDrag(false),
          onDrop: (e) => { e.preventDefault(); setDrag(false); take(e.dataTransfer.files && e.dataTransfer.files[0]) },
          title: asset ? '点击预览参考视频；用「替换」换片' : '点击或拖入参考视频',
        },
          asset ? h('video', { src: mediaUrl(asset.path), muted: true, playsInline: true }) : h('div', { className: 'adp-drop-empty' },
            h('b', null, busy ? '上传中…' : '拖入参考视频'),
            h('span', null, '或点击选择 · mp4 / mov / webm · ≤30s')
          ),
          asset ? h('div', { className: 'adp-drop-overlay' },
            h('span', { style: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, asset.name),
            h('span', { className: 'adp-drop-actions' },
              h('button', { className: 'adp-btn ghost adp-drop-action', onClick: (e) => { e.stopPropagation(); choose() }, title: '替换参考视频' }, '替换'),
              h('button', { className: 'adp-remove', onClick: (e) => { e.stopPropagation(); onAsset(null) }, title: '移除' }, '×')
            )
          ) : null
        ),
        h('input', { ref: input, type: 'file', accept: 'video/*', style: { display: 'none' }, onChange: (e) => { take(e.currentTarget.files && e.currentTarget.files[0]); e.currentTarget.value = '' } }),
        err ? h('div', { className: 'adp-error' }, err) : null
      )
    }

    function MediaGrid({ assets, onAdd, onRemove, onPreview, max = 9 }) {
      const input = useRef(null)
      const [busy, setBusy] = useState(false)
      const [err, setErr] = useState('')
      const add = async (files) => {
        const list = Array.from(files || []).slice(0, Math.max(0, max - (assets || []).length))
        if (!list.length) return
        setBusy(true); setErr('')
        try {
          const out = []
          for (const file of list) out.push(await uploadFile(file, 'image'))
          onAdd(out)
        } catch (e) { setErr(String(e.message || e)) } finally { setBusy(false) }
      }
      return h('div', { className: 'adp-col' },
        h('div', { className: 'adp-media-grid' },
          (assets || []).map((asset) => h('div', {
            className: 'adp-media' + (onPreview ? ' has-preview' : ''),
            key: asset.id,
            title: asset.name + ' · 点击预览',
            role: onPreview ? 'button' : undefined,
            tabIndex: onPreview ? 0 : undefined,
            onClick: onPreview ? () => onPreview(asset) : undefined,
            onKeyDown: onPreview ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onPreview(asset) } } : undefined,
          },
            h('img', { src: mediaUrl(asset.path), alt: asset.name }),
            h('button', { className: 'adp-remove', onClick: (e) => { e.stopPropagation(); onRemove(asset.id) }, title: '移除' }, '×')
          )),
          (assets || []).length < max ? h('button', { className: 'adp-media-add', onClick: () => input.current && input.current.click(), disabled: busy, title: '添加商品图' },
            h('b', null, busy ? '…' : '+'),
            h('span', null, busy ? '上传中' : '添加')
          ) : null
        ),
        h('input', { ref: input, type: 'file', accept: 'image/*', multiple: true, style: { display: 'none' }, onChange: (e) => { add(e.currentTarget.files); e.currentTarget.value = '' } }),
        err ? h('div', { className: 'adp-error' }, err) : null
      )
    }

    function PersonaFields({ value, onChange, columns = 4 }) {
      const v = value || {}
      const set = (key, val) => onChange(Object.assign({}, v, { [key]: val }))
      return h('div', { className: 'adp-field-grid g' + columns },
        h(FormSelect, { label: '性别', value: v.gender || 'any', onChange: (x) => set('gender', x), options: [{ value: 'any', label: '不限' }, { value: 'female', label: '女' }, { value: 'male', label: '男' }] }),
        h(FormSelect, { label: '年龄', value: v.age || 'youth', onChange: (x) => set('age', x), options: [{ value: 'teenager', label: '18–24 青年感' }, { value: 'youth', label: '25–34 青年' }, { value: 'middle_aged', label: '35–54 中年' }, { value: 'senior', label: '55+ 老年' }] }),
        h(FormSelect, { label: '体型', value: v.body_type || 'standard', onChange: (x) => set('body_type', x), options: [{ value: 'slim', label: '偏瘦' }, { value: 'standard', label: '标准' }, { value: 'athletic', label: '健硕' }, { value: 'chubby', label: '微胖' }] }),
        h(FormSelect, { label: '族裔', value: v.ethnicity || 'asian', onChange: (x) => set('ethnicity', x), options: [{ value: 'asian', label: '亚洲' }, { value: 'caucasian', label: '欧美' }, { value: 'latino', label: '拉美' }, { value: 'african', label: '非洲' }, { value: 'middle_eastern', label: '中东' }, { value: 'any', label: '不限' }] })
      )
    }

    function AdvancedRow({ value, onChange, models, needsDialogue, autoModel, autoTiming, timingNote, aspectNote }) {
      const v = value || {}
      const set = (key, val) => onChange(Object.assign({}, v, { [key]: val }))
      const usableModels = (models || []).filter(m => m.available && m.enabled !== false)
      const modelOptions = usableModels.map(m => ({ value: m.id, label: m.label }))
      const currentModel = modelOptions.some(o => o.value === v.model) ? v.model : (modelOptions[0] ? modelOptions[0].value : '')
      return h('div', { className: 'adp-col', style: { gap: 9 } },
        h('div', { className: 'adp-field-grid g3' },
          h(FormSelect, { label: '模式', value: v.generation_mode || 'fast', onChange: (x) => set('generation_mode', x), options: [{ value: 'fast', label: '快速 · 整条' }, { value: 'fine', label: '精细 · 分段' }] }),
          autoTiming
            ? h('div', { className: 'adp-field' }, h('div', { className: 'adp-field-label' }, '时长'), h('div', { className: 'adp-small adp-muted', style: { paddingTop: 8 } }, timingNote || '跟随参考片'))
            : h(FormSelect, { label: '时长（秒）', value: v.duration || 12, onChange: (x) => set('duration', Number(x)), options: [5, 8, 10, 12, 15, 30] }),
          autoTiming
            ? h('div', { className: 'adp-field' }, h('div', { className: 'adp-field-label' }, '比例'), h('div', { className: 'adp-small adp-muted', style: { paddingTop: 8 } }, aspectNote || '跟随参考片'))
            : h(FormSelect, { label: '比例', value: v.aspect || '9:16', onChange: (x) => set('aspect', x), options: ['9:16', '16:9', '1:1', '4:3', '3:4', '21:9'] })
        ),
        h('div', { className: 'adp-field-grid g3' },
          h(FormSelect, { label: '清晰度', value: v.resolution || '720p', onChange: (x) => set('resolution', x), options: ['480p', '720p', '1080p'] }),
          autoModel
            ? h('div', { className: 'adp-field' }, h('div', { className: 'adp-field-label' }, '模型'), h('div', { className: 'adp-small adp-muted', style: { paddingTop: 8 } }, '自动选择（H3 完整复刻优先）'))
            : h(FormSelect, { label: '模型', value: currentModel, onChange: (x) => set('model', x), options: modelOptions }),
          h(FormSelect, { label: '字幕', value: v.subtitle || 'off', onChange: (x) => set('subtitle', x), options: [{ value: 'off', label: '不启用' }, { value: 'sidecar', label: 'SRT 旁挂' }] })
        )
      )
    }

    function StatusBadge({ status }) {
      const cls = status === 'succeeded' ? 'ok' : status === 'failed' || status === 'canceled' ? 'bad' : status === 'running' || status === 'queued' ? 'warn' : ''
      const label = { queued: '排队', running: '生成中', succeeded: '完成', failed: '失败', canceled: '已取消', interrupted: '中断' }[status] || status
      return h(Badge, { status: cls }, label)
    }

    function RunCard({ run, onOpen }) {
      return h('div', { className: 'adp-run-card', onClick: () => onOpen(run) },
        h('div', { className: 'adp-row' }, h('div', { className: 'adp-h2 adp-grow' }, run.title || run.scenario), h(StatusBadge, { status: run.status })),
        h('div', { className: 'adp-small adp-muted', style: { marginTop: 4 } }, run.scenario === 'text-to-image' ? ('文生图片 · ' + ((run.advanced && run.advanced.aspect) || '1:1') + ' · ' + ((run.advanced && run.advanced.area) || '2K')) : (run.scenario + ' · ' + ((run.advanced && run.advanced.duration) || 0) + 's · ' + ((run.advanced && run.advanced.aspect) || '9:16'))),
        h('div', { className: 'adp-progress', style: { marginTop: 8 } }, h('i', { style: { width: Math.round((run.progress || 0) * 100) + '%' } })),
        h('div', { className: 'adp-small adp-faint', style: { marginTop: 5 } }, run.step || '—', run.error ? ' · ' + String(run.error).slice(0, 80) : '')
      )
    }

    async function downloadExport(runId) {
      const res = await fetch(API + '/runs/' + runId + '/export', { headers: { 'x-adplus-token': TOKEN } })
      if (!res.ok) throw new Error('导出失败')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = runId + '.zip'
      a.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    }

    function ImageResultPanel({ run, onChanged, onBack }) {
      const result = run.result || {}
      const [busy, setBusy] = useState('')
      const [err, setErr] = useState('')
      const retry = async () => {
        setBusy('retry'); setErr('')
        try { const d = await api('/images/' + run.id + '/retry', { method: 'POST' }); onChanged && onChanged(d.run) } catch (e) { setErr(String(e.message || e)); } finally { setBusy('') }
      }
      const download = () => {
        const url = mediaUrl(result.image)
        if (!url) return
        const a = document.createElement('a')
        a.href = url
        a.download = 'adplus-' + run.id + '.jpg'
        a.click()
      }
      const copy = async () => { try { await navigator.clipboard.writeText(result.prompt || '') } catch (e) { setErr('复制失败：' + String(e.message || e)) } }
      return h('div', { className: 'adp-image-result' },
        h('div', { className: 'adp-result-head' },
          h('button', { className: 'adp-back', onClick: onBack, title: '返回' }, h(Glyph, { name: 'back', size: 15 }), h('span', null, '返回')),
          h('div', { className: 'adp-result-title' }, h('div', { className: 'adp-h1' }, run.title || '图片结果'), h('div', { className: 'adp-small adp-muted' }, '文生图片 · ' + (result.aspect || (run.advanced || {}).aspect || '1:1') + ' · ' + (result.area || (run.advanced || {}).area || '2K'))),
          h('div', { className: 'adp-result-badges' }, h(StatusBadge, { status: run.status }), h(Badge, { status: 'ok' }, '图片'))
        ),
        run.error ? h('div', { className: 'adp-result-error' }, run.error) : null,
        (result.warnings || []).length ? h('div', { className: 'adp-notice', style: { marginBottom: 10 } }, result.warnings.join('；')) : null,
        h('div', { className: 'adp-image-grid' },
          h('div', { className: 'adp-image-stage' }, result.image ? h('img', { src: mediaUrl(result.image), alt: result.prompt || 'generated image' }) : h('div', { className: 'adp-empty-stage' }, run.status === 'running' ? '正在生成图片…' : '还没有图片')),
          h('aside', { className: 'adp-result-side' },
            h('div', { className: 'adp-side-block' },
              h('div', { className: 'adp-side-label' }, '图片操作'),
              h('div', { className: 'adp-action-list' },
                h('button', { className: 'adp-action', onClick: retry, disabled: run.status === 'running' || busy === 'retry' }, h(Glyph, { name: 'refresh' }), h('span', null, busy === 'retry' ? '提交中…' : '再生成')),
                h('button', { className: 'adp-action', onClick: download, disabled: !result.image }, h(Glyph, { name: 'download' }), h('span', null, '下载')),
                h('button', { className: 'adp-action', onClick: copy, disabled: !result.prompt }, h(Glyph, { name: 'copy' }), h('span', null, '复制 prompt'))
              )
            ),
            h('div', { className: 'adp-side-block' },
              h('div', { className: 'adp-side-label' }, '图片信息'),
              h('div', { className: 'adp-facts' },
                h('div', { className: 'adp-fact' }, h('span', null, '模型'), h('b', null, result.native_model || result.model || '—')),
                h('div', { className: 'adp-fact' }, h('span', null, '尺寸'), h('b', null, result.width && result.height ? result.width + '×' + result.height : (result.area || '—'))),
                h('div', { className: 'adp-fact' }, h('span', null, '比例'), h('b', null, result.aspect || '—')),
                h('div', { className: 'adp-fact' }, h('span', null, '资产'), h('b', null, result.asset_id || '—'))
              )
            ),
            h('div', { className: 'adp-side-block' },
              h('div', { className: 'adp-side-label' }, 'Prompt'),
              h('div', { className: 'adp-image-prompt' }, result.prompt || (run.inputs && run.inputs.prompt) || '—')
            ),
            err ? h('div', { className: 'adp-result-error' }, err) : null
          )
        )
      )
    }

    function ResultPanel({ run, onChanged, onBack, assets }) {
      if (run.scenario === 'text-to-image') return h(ImageResultPanel, { run, onChanged, onBack })
      return h(VideoResultPanel, { run, onChanged, onBack, assets })
    }

    function VideoResultPanel({ run, onChanged, onBack, assets }) {
      const [storyboard, setStoryboard] = useState([])
      const [analysis, setAnalysis] = useState(null)
      const [selected, setSelected] = useState(null)
      const [msg, setMsg] = useState('')
      const [chat, setChat] = useState([])
      const [changes, setChanges] = useState([])
      const [busy, setBusy] = useState('')
      const [err, setErr] = useState('')
      const [editOpen, setEditOpen] = useState(false)
      const [promptOpen, setPromptOpen] = useState(false)
      const [promptText, setPromptText] = useState('')
      const [promptMeta, setPromptMeta] = useState(null)
      const [promptBusy, setPromptBusy] = useState('')
      const [promptSaved, setPromptSaved] = useState(false)
      const adv = run.advanced || {}
      const inputs = run.inputs || {}
      const brief = String(inputs.brief || '').trim()
      const refAsset = (assets || []).find((a) => a.id === inputs.reference_asset_id)
      const productAssets = (inputs.product_asset_ids || []).map((id) => (assets || []).find((a) => a.id === id)).filter(Boolean)
      const persona = adv.persona || {}
      const [edit, setEdit] = useState({ aspect: adv.aspect || '9:16', resolution: adv.resolution || '720p', duration: adv.duration || 12 })
      const result = run.result || {}
      const video = result.video ? mediaUrlVersion(result.video, run.version) : ''
      const qa = result.qa
      const postOnly = changes.length > 0 && changes.every((c) => c.stage === 'post')
      const h3Mode = (run.selection || {}).mode === 'h3_reference'
      const running = run.status === 'running' || run.status === 'queued'
      const editDirty = edit.aspect !== (adv.aspect || '9:16') || edit.resolution !== (adv.resolution || '720p') || Number(edit.duration) !== Number(adv.duration || 12)
      const hasEdits = (run.segment_edits || []).length > 0

      useEffect(() => {
        setStoryboard([]); setAnalysis(null); setSelected(null); setChat([]); setChanges([]); setBusy(''); setErr(''); setEditOpen(false)
        setPromptOpen(false); setPromptText(''); setPromptMeta(null); setPromptBusy(''); setPromptSaved(false)
        setEdit({ aspect: adv.aspect || '9:16', resolution: adv.resolution || '720p', duration: adv.duration || 12 })
      }, [run.id])

      const loadPrompt = useCallback(async () => {
        setPromptBusy('load'); setErr('')
        try {
          const data = await api('/runs/' + run.id + '/prompt')
          setPromptMeta(data)
          setPromptText(String(data.text || ''))
          setPromptSaved(false)
        } catch (e) { setErr(String(e.message || e)) } finally { setPromptBusy('') }
      }, [run.id])

      const togglePrompt = () => {
        setPromptOpen(!promptOpen)
      }

      // Prompt text follows the run: a segment edit or regeneration bumps the
      // version, and a stale preview would show the previous copy.
      useEffect(() => {
        if (!promptOpen) return
        void loadPrompt()
      }, [promptOpen, run.id, run.version, loadPrompt])

      const savePrompt = async () => {
        setPromptBusy('save'); setErr('')
        try {
          await api('/runs/' + run.id + '/prompt-override', { method: 'POST', body: { text: promptText } })
          setPromptSaved(true)
          await loadPrompt()
        } catch (e) { setErr(String(e.message || e)) } finally { setPromptBusy('') }
      }

      const submitPrompt = async () => {
        setPromptBusy('submit'); setErr('')
        try {
          await api('/runs/' + run.id + '/prompt-override', { method: 'POST', body: { text: promptText } })
          const data = await api('/runs/' + run.id + '/retry', { method: 'POST' })
          setPromptSaved(true)
          onChanged && onChanged(data.run)
        } catch (e) { setErr(String(e.message || e)) } finally { setPromptBusy('') }
      }

      const copyPrompt = async () => {
        try { await navigator.clipboard.writeText(promptText); setPromptSaved(false); setErr('') } catch (e) { setErr('复制失败，请手动选择文本') }
      }

      const loadSb = useCallback(async () => {
        setBusy('sb'); setErr('')
        try {
          const data = await api('/runs/' + run.id + '/storyboard')
          setStoryboard(data.segments || [])
        } catch (e) { setErr(String(e.message || e)) } finally { setBusy('') }
      }, [run.id])

      useEffect(() => { if (run.status === 'succeeded' || (run.result && run.result.video)) void loadSb() }, [run.status, run.result, run.version, loadSb])

      const loadAnalysis = useCallback(async () => {
        if (run.scenario !== 'viral-remake') return
        try { setAnalysis(await api('/runs/' + run.id + '/analysis')) } catch { setAnalysis(null) }
      }, [run.id, run.scenario])
      useEffect(() => { if (run.status === 'succeeded' || (run.result && run.result.video)) void loadAnalysis() }, [run.status, run.result, run.version, loadAnalysis])

      const openEdit = () => {
        setEdit({ aspect: adv.aspect || '9:16', resolution: adv.resolution || '720p', duration: adv.duration || 12 })
        setEditOpen(true)
      }

      const applyEdit = async () => {
        if (!editDirty) return
        setBusy('edit'); setErr('')
        try {
          const list = []
          if (edit.aspect !== (adv.aspect || '9:16')) list.push({ field: 'advanced.aspect', from: adv.aspect, to: edit.aspect, stage: 'generate', requires_regeneration: true, label: '比例' })
          if (edit.resolution !== (adv.resolution || '720p')) list.push({ field: 'advanced.resolution', from: adv.resolution, to: edit.resolution, stage: 'generate', requires_regeneration: true, label: '清晰度' })
          if (Number(edit.duration) !== Number(adv.duration || 12)) list.push({ field: 'advanced.duration', from: adv.duration, to: Number(edit.duration), stage: 'generate', requires_regeneration: true, label: '时长（秒）' })
          const data = await api('/runs/' + run.id + '/derive', { method: 'POST', body: { changes: list } })
          setEditOpen(false)
          onChanged && onChanged(data.run)
        } catch (e) { setErr(String(e.message || e)) } finally { setBusy('') }
      }

      const selectSegment = (seg) => {
        if (selected && selected.id === seg.id) { setSelected(null); return }
        setSelected(seg); setChat([]); setChanges([]); setMsg(''); setErr('')
      }

      const send = async () => {
        if (!msg.trim() || !selected) return
        const text = msg.trim(); setMsg(''); setChat((prev) => prev.concat([{ role: 'user', text }])); setBusy('chat'); setErr('')
        try {
          const data = await api('/assistant', { method: 'POST', body: {
            message: text,
            selected_segment_id: selected.id,
            context: { advanced: adv, persona: adv.persona || {}, post: adv, brief: (run.inputs && run.inputs.brief) || '' },
          } })
          setChat((prev) => prev.concat([{ role: 'assistant', text: data.reply || '已整理变更。' }]))
          setChanges(data.changes || [])
        } catch (e) { setErr(String(e.message || e)) } finally { setBusy('') }
      }

      const applyChanges = async () => {
        if (!changes.length) return
        setBusy('apply'); setErr('')
        try {
          const rewrite = changes.find((c) => c.field === 'segment.rewrite' && selected)
          const path = rewrite
            ? '/runs/' + run.id + '/segments/' + selected.id + '/edit'
            : selected && !postOnly
              ? '/runs/' + run.id + '/segments/' + selected.id + '/replace'
              : '/runs/' + run.id + '/derive'
          const body = rewrite ? { instruction: String(rewrite.to) } : { changes }
          const data = await api(path, { method: 'POST', body })
          setChanges([]); setChat([])
          onChanged && onChanged(data.run)
        } catch (e) { setErr(String(e.message || e)) } finally { setBusy('') }
      }

      const retry = async () => {
        setBusy('retry'); setErr('')
        try { const d = await api('/runs/' + run.id + '/retry', { method: 'POST' }); onChanged && onChanged(d.run) } catch (e) { setErr(String(e.message || e)) } finally { setBusy('') }
      }
      const cancel = async () => {
        try { const d = await api('/runs/' + run.id + '/cancel', { method: 'POST' }); onChanged && onChanged(d.run) } catch (e) { setErr(String(e.message || e)) }
      }
      const rollback = async () => {
        setBusy('rollback'); setErr('')
        try { const d = await api('/runs/' + run.id + '/rollback', { method: 'POST' }); onChanged && onChanged(d.run) } catch (e) { setErr(String(e.message || e)) } finally { setBusy('') }
      }
      const download = async () => {
        setBusy('download'); setErr('')
        try { await downloadExport(run.id) } catch (e) { setErr(String(e.message || e)) } finally { setBusy('') }
      }

      const aspectOptions = Array.from(new Set(['9:16', '16:9', '1:1', '4:3', '3:4', '21:9', adv.aspect].filter(Boolean)))
      const resolutionOptions = Array.from(new Set(['480p', '720p', '1080p', adv.resolution].filter(Boolean)))
      const durationOptions = Array.from(new Set([4, 5, 6, 8, 10, 12, 15, 30, Number(adv.duration || 12)])).sort((a, b) => a - b)
      const copyBrief = async () => {
        try { await navigator.clipboard.writeText(brief) } catch (e) { setErr('复制失败：' + String(e.message || e)) }
      }

      const selection = run.selection || {}
      const selectionLabel = {
        h3_reference: 'H3 完整复刻',
        reference: '参考复刻',
        reference_fallback: '参考复刻',
        keyframe: '关键帧锚定',
        generation: '按拆解生成',
        generation_fallback: '按拆解生成',
        analysis_only: '仅拆解'
      }[selection.mode] || selection.mode || '自动'
      const facts = [
        ['版本', 'v' + (run.version || 1)],
        ['画幅', selection.source_aspect || adv.aspect || '9:16'],
        ['清晰度', adv.resolution || '720p'],
        ['时长', result.duration_s ? fmt(result.duration_s) : (adv.duration ? adv.duration + 's' : '—')],
        ['模型', result.model || selection.model || adv.model || 'auto'],
        ['复刻', selectionLabel],
        ['口播', result.audio_source === 'reference' ? '参考片原声' : result.audio_source === 'h3' ? 'H3 新生成' : '—'],
      ]
      const qaPass = (qa && qa.summary && qa.summary.pass) || 0
      const qaTotal = (qa && qa.checks && qa.checks.length) || 0
      const qaVoiceChecked = !qa || qa.asr_available !== false
      const qaNotes = (qa && qa.checks ? qa.checks : [])
        .filter((c) => c.status !== 'pass')
        .filter((c) => qaVoiceChecked || !(String(c.id).startsWith('req_') || c.id === 'audio_copy' || c.id === 'audio_overlap'))

      return h('div', { className: 'adp-result' },
        h('div', { className: 'adp-result-head' },
          h('button', { className: 'adp-back', onClick: onBack, title: '返回' }, h(Glyph, { name: 'back', size: 15 }), h('span', null, '返回')),
          h('div', { className: 'adp-result-title' },
            h('div', { className: 'adp-h1' }, run.title || '成片'),
            h('div', { className: 'adp-small adp-muted' }, 'v' + (run.version || 1) + ' · ' + (adv.aspect || '9:16') + ' · ' + (adv.resolution || '720p') + (result.duration_s ? ' · ' + fmt(result.duration_s) : ''))
          ),
          h('div', { className: 'adp-result-badges' }, h(StatusBadge, { status: run.status }))
        ),
        run.error ? h('div', { className: 'adp-error' }, run.error) : null,
        h('div', { className: 'adp-result-grid' },
          h('div', { className: 'adp-stage' },
            video ? h('video', { className: 'adp-stage-video', src: video, controls: true, playsInline: true, poster: storyboard[0] && storyboard[0].thumbnail ? mediaUrlVersion(storyboard[0].thumbnail, run.version) : undefined }) : h('div', { className: 'adp-empty-stage' }, running ? '正在生成…' : '还没有可播放的成片'),
            running ? h('div', { className: 'adp-stage-progress' }, h('div', { className: 'adp-progress' }, h('i', { style: { width: Math.round((run.progress || 0) * 100) + '%' } })), h('span', null, '生成中 · ' + Math.round((run.progress || 0) * 100) + '%')) : null
          ),
          h('aside', { className: 'adp-result-side' },
            h('div', { className: 'adp-side-block' },
              h('div', { className: 'adp-side-label' }, '成片操作'),
              h('div', { className: 'adp-action-list' },
                h('button', { className: 'adp-action', onClick: openEdit, disabled: running || !video, title: '调整比例、清晰度或时长，生成新版本' }, h(Glyph, { name: 'edit' }), h('span', null, '修改参数')),
                h('button', { className: 'adp-action', onClick: retry, disabled: running || busy === 'retry', title: '保持当前参数，再生成一条' }, h(Glyph, { name: 'refresh' }), h('span', null, busy === 'retry' ? '提交中…' : '再生成')),
                h('button', { className: 'adp-action', onClick: download, disabled: !video || busy === 'download', title: '下载成片与字幕压缩包' }, h(Glyph, { name: 'download' }), h('span', null, busy === 'download' ? '打包中…' : '下载')),
                hasEdits ? h('button', { className: 'adp-action', onClick: rollback, disabled: running || busy === 'rollback', title: '回滚上一次分镜替换' }, h(Glyph, { name: 'undo' }), h('span', null, busy === 'rollback' ? '回滚中…' : '回滚上一镜')) : null,
                running ? h('button', { className: 'adp-action danger', onClick: cancel }, h(Glyph, { name: 'close' }), h('span', null, '取消生成')) : null
              ),
              h('div', { className: 'adp-side-note' }, '「再生成」保设置换一条；「修改参数」改设置生成新版本；单镜编辑只重做该镜并可直接回滚。')
            ),
            h('div', { className: 'adp-side-block' },
              h('div', { className: 'adp-side-label' }, '成片信息'),
              h('div', { className: 'adp-facts' }, facts.map((f) => h('div', { key: f[0], className: 'adp-fact' }, h('span', null, f[0]), h('b', null, f[1]))))
            ),
            qa ? h('div', { className: 'adp-side-block' },
              h('div', { className: 'adp-side-label' }, '质量检查'),
              qa.remake_score ? h('div', { className: 'adp-qa' },
                h(Badge, { status: qa.remake_score.passed === false ? 'bad' : 'ok' }, '复刻度 ' + qa.remake_score.total + (qa.remake_score.threshold ? '/' + qa.remake_score.threshold : '')),
                h('span', { className: 'adp-small adp-muted' }, qa.remake_score.passed === false ? '低于本档及格线' : '达到本档及格线')
              ) : null,
              h('div', { className: 'adp-qa' },
                h(Badge, { status: (qa.summary && qa.summary.fail) ? 'bad' : 'ok' }, qaPass + '/' + qaTotal),
                h('span', { className: 'adp-small adp-muted' }, (qa.summary && qa.summary.shippable) ? '可交付' : '需要复核')
              ),
              qaNotes.map((c) => h('div', { key: c.id, className: 'adp-qa-note' }, c.label + '：' + c.status + (c.note ? ' · ' + c.note : ''))),
              qaVoiceChecked ? null : h('div', { className: 'adp-qa-note' }, '未安装语音识别，口播与需求校验已折叠（安装后可自动核对）')
            ) : null,
            result.post_notes && result.post_notes.length ? h('div', { className: 'adp-side-block' }, h('div', { className: 'adp-side-label' }, '后期说明'), h('div', { className: 'adp-side-note' }, result.post_notes.join(' · '))) : null
          )
        ),
        h('section', { className: 'adp-inputs' },
          h('div', { className: 'adp-inputs-head' },
            h('div', { className: 'adp-h2' }, '创作输入'),
            h('span', { className: 'adp-storyboard-meta' }, '保留原始需求，方便复现和追溯')
          ),
          h('div', { className: 'adp-inputs-grid' },
            h('div', { className: 'adp-input-brief' },
              h('div', { className: 'adp-input-label' }, '原始需求'),
              h('div', { className: 'adp-brief-text' }, brief || '未填写'),
              brief ? h('button', { className: 'adp-copy', onClick: copyBrief, title: '复制原始需求' }, h(Glyph, { name: 'copy' }), h('span', null, '复制')) : null
            ),
            h('div', { className: 'adp-input-assets' },
              h('div', { className: 'adp-input-label' }, '素材与人物'),
              refAsset ? h('div', { className: 'adp-asset-line' },
                h('span', { className: 'adp-asset-tag' }, '参考视频'),
                h('span', { className: 'adp-asset-name', title: refAsset.name }, refAsset.name || refAsset.id)
              ) : h('div', { className: 'adp-small adp-muted' }, '无参考视频'),
              productAssets.length ? h('div', { className: 'adp-asset-line' },
                h('span', { className: 'adp-asset-tag' }, '商品图'),
                h('div', { className: 'adp-asset-thumbs' }, productAssets.map((a) => h('span', { key: a.id, className: 'adp-asset-thumb', title: a.name }, h('img', { src: mediaUrl(a.path), alt: '' })))),
                h('span', { className: 'adp-small adp-muted' }, productAssets.length + ' 张')
              ) : h('div', { className: 'adp-small adp-muted' }, '无商品图'),
              h('div', { className: 'adp-asset-line' },
                h('span', { className: 'adp-asset-tag' }, '模特'),
                h('span', { className: 'adp-small adp-muted' }, [persona.gender, persona.age, persona.body_type, persona.ethnicity].filter(Boolean).join(' · ') || '未指定')
              )
            )
          )
        ),
        analysis && analysis.available ? h('section', { className: 'adp-inputs' },
          h('div', { className: 'adp-inputs-head' },
            h('div', { className: 'adp-h2' }, '参考片拆解'),
            h('span', { className: 'adp-storyboard-meta' }, (analysis.analysis && analysis.analysis.mode === 'frames' ? '视频帧分析' : '启发式拆解') + ((analysis.analysis && analysis.analysis.model) ? ' · ' + analysis.analysis.model : '') + ((analysis.analysis && analysis.analysis.degraded) ? ' · 降级' : ''))
          ),
          h('div', { className: 'adp-col', style: { padding: '0 14px 14px', gap: 8 } },
            ((analysis.remake_plan || {}).shots || []).map((shot) => h('div', { key: shot.id, className: 'adp-shot', style: { padding: '9px 10px' } },
              h('div', { className: 'adp-shot-top' },
                h('b', null, (shot.camera && shot.camera.shot_size) || '镜头'),
                h('span', { className: 'adp-shot-time' }, fmtAt(shot.start_s) + '–' + fmtAt(shot.end_s))
              ),
              h('div', { className: 'adp-shot-dialogue' }, shot.action || '—'),
              h('div', { className: 'adp-shot-action' }, [shot.scene, (shot.product || {}).name, (shot.cast || []).map((x) => x.description).filter(Boolean).join('、')].filter(Boolean).join(' · ') || '—'),
              (shot.dialogue_rows || []).length
                ? h('div', { className: 'adp-small adp-muted' }, shot.dialogue_rows.map((row) => fmtAt(row.start_s) + ' ' + row.text).join(' / '))
                : ((shot.dialogue || []).length ? h('div', { className: 'adp-small adp-muted' }, shot.dialogue.join(' / ')) : null)
            )),
            (analysis.analysis && analysis.analysis.asr && analysis.analysis.asr.source && analysis.analysis.asr.source !== 'asr')
              ? h('div', { className: 'adp-small adp-muted' }, '台词未解析：' + (analysis.analysis.asr.error || analysis.analysis.asr.source))
              : ((analysis.analysis && analysis.analysis.asr && analysis.analysis.asr.error)
                ? h('div', { className: 'adp-small adp-muted' }, '台词校对提示：' + analysis.analysis.asr.error)
                : null),
            (analysis.analysis && analysis.analysis.reason) ? h('div', { className: 'adp-small adp-muted' }, analysis.analysis.reason) : null
          )
        ) : null,
        h('section', { className: 'adp-storyboard' },
          h('div', { className: 'adp-storyboard-head' },
            h('div', { className: 'adp-h2' }, '分镜'),
            h('span', { className: 'adp-storyboard-meta' }, storyboard.length ? storyboard.length + ' 段 · ' + (run.generation_mode === 'fine' ? '精细模式' : '快速模式') : (running ? '生成中…' : (busy === 'sb' ? '读取中…' : '还没有分镜')))
          ),
          storyboard.length ? storyboard.map((seg) => h('div', { key: seg.id, className: 'adp-shot' + (selected && selected.id === seg.id ? ' open' : '') },
            h('div', { className: 'adp-shot-thumb' },
              h('div', { className: 'adp-shot-placeholder' }),
              seg.thumbnail ? h('img', { src: mediaUrlVersion(seg.thumbnail, run.version), alt: '', onError: (e) => { e.currentTarget.style.display = 'none' } }) : null,
              h('span', { className: 'adp-shot-index' }, '#' + (seg.index + 1)),
              busy === 'apply' && selected && selected.id === seg.id ? h('div', { className: 'adp-shot-loading' }, '生成中') : null
            ),
            h('div', { className: 'adp-shot-body' },
              h('div', { className: 'adp-shot-top' },
                h('b', null, seg.function || '镜头'),
                h('span', { className: 'adp-shot-time' }, fmtAt(seg.start_s) + '–' + fmtAt(seg.end_s)),
                h('span', { className: 'adp-shot-time' }, fmtAt(seg.end_s - seg.start_s))
              ),
              (seg.lines || []).length
                ? h('div', { className: 'adp-shot-lines' }, seg.lines.map((row, i) => h('div', { key: i },
                    h('span', { className: 'adp-line-at' }, fmtAt(row.start_s) + '–' + fmtAt(row.end_s) + ' '), row.text)))
                : h('div', { className: 'adp-shot-lines' }, (seg.dialogue || '—').split(' / ').filter(Boolean).map((line, i) => h('div', { key: i }, line))),
              seg.action ? h('div', { className: 'adp-shot-action' }, seg.action) : null
            ),
            h('button', { className: 'adp-shot-edit', onClick: () => selectSegment(seg), 'aria-expanded': selected && selected.id === seg.id, title: '编辑这一镜' }, h(Glyph, { name: 'edit' }), h('span', null, selected && selected.id === seg.id ? '收起' : '编辑')),
            selected && selected.id === seg.id ? h('div', { className: 'adp-shot-editor' },
              h('div', { className: 'adp-shot-editor-head' }, '分镜助手 · #' + (seg.index + 1) + ' · ' + fmtAt(seg.start_s) + '–' + fmtAt(seg.end_s) + (h3Mode ? ' · H3 整条重生成' : '')),
              h3Mode ? h('div', { className: 'adp-small adp-muted' }, 'H3 是整条参考复刻，提交后会生成新版本并重跑整条，父版本不受影响。') : null,
              chat.length ? h('div', { className: 'adp-chat' }, chat.map((m, i) => h('div', { key: i, className: 'adp-msg ' + (m.role === 'user' ? 'user' : '') }, m.text))) : h('div', { className: 'adp-small adp-muted' }, '直接说这一镜要改什么，例如：人物更近、把价格说出来、结尾加抢购动作。'),
              changes.length ? h('div', { className: 'adp-col' }, changes.map((c, i) => h('div', { key: i, className: 'adp-change' }, (c.label || c.field) + '：' + JSON.stringify(c.from) + ' → ' + JSON.stringify(c.to) + (c.stage === 'generate' ? ' · 需要重生成' : ' · 后期')))) : null,
              h('div', { className: 'adp-row adp-shot-chat-row' },
                h('input', { className: 'adp-input adp-grow', value: msg, placeholder: '这一镜改成…', onChange: (e) => setMsg(e.currentTarget.value), onKeyDown: (e) => { if (e.key === 'Enter') send() } }),
                h('button', { className: 'adp-btn primary', onClick: send, disabled: busy === 'chat' }, '发送'),
                changes.length ? h('button', { className: 'adp-btn', onClick: applyChanges, disabled: busy === 'apply' }, postOnly ? '只应用后期修改' : (h3Mode ? '整条重新生成（H3）' : '应用到这一镜')) : null
              )
            ) : null
          )) : h('div', { className: 'adp-empty-shots' },
            h('span', null, running ? '正在生成，分镜稍后出现…' : (busy === 'sb' ? '正在读取分镜…' : '还没有分镜数据。')),
            !busy && !running ? h('button', { className: 'adp-btn ghost', onClick: loadSb }, '重新读取') : null
          )
        ),
        run.scenario === 'viral-remake' && !running && !(analysis && analysis.available) ? h('section', { className: 'adp-inputs' },
          h('div', { className: 'adp-inputs-head' },
            h('div', { className: 'adp-h2' }, '参考片拆解'),
            h('span', { className: 'adp-storyboard-meta' }, '拆解中…')
          ),
          h('div', { className: 'adp-empty-shots' }, h('span', null, '正在分析镜头、场景与台词，完成后自动出现。'))
        ) : null,
        run.scenario === 'viral-remake' && analysis && analysis.available ? h('section', { className: 'adp-storyboard' },
          h('div', { className: 'adp-storyboard-head' },
            h('div', { className: 'adp-h2' }, '生成提示词'),
            h('div', { className: 'adp-row', style: { gap: 10, alignItems: 'center' } },
              h('span', { className: 'adp-storyboard-meta' },
                promptMeta
                  ? [promptMeta.mode || 'generation', promptMeta.shots + ' 镜', promptMeta.lines + ' 句台词', promptMeta.chars + ' 字'].join(' · ')
                  : '查看本次实际发给视频模型的提示词'
              ),
              h('button', { className: 'adp-btn ghost', onClick: togglePrompt, disabled: promptBusy === 'load' }, promptOpen ? '收起' : (promptBusy === 'load' ? '读取中…' : '预览'))
            )
          ),
          promptOpen ? h('div', { className: 'adp-col', style: { padding: '0 14px 14px', gap: 8 } },
            h('textarea', {
              className: 'adp-input',
              style: { minHeight: 220, resize: 'vertical', fontFamily: 'inherit', fontSize: 12, lineHeight: 1.55 },
              value: promptText,
              onChange: (e) => { setPromptText(e.currentTarget.value); setPromptSaved(false) },
            }),
            h('div', { className: 'adp-row', style: { gap: 8, alignItems: 'center' } },
              h('button', { className: 'adp-btn primary', onClick: submitPrompt, disabled: promptBusy === 'submit' || promptBusy === 'save' }, promptBusy === 'submit' ? '提交中…' : '用这段提示词重新生成'),
              h('button', { className: 'adp-btn', onClick: savePrompt, disabled: promptBusy === 'submit' || promptBusy === 'save' }, promptBusy === 'save' ? '保存中…' : '仅保存'),
              h('button', { className: 'adp-btn', onClick: copyPrompt }, '复制'),
              promptSaved ? h('span', { className: 'adp-small adp-muted' }, '已保存；重新生成时按这段文字发给模型') : null
            ),
            h('div', { className: 'adp-small adp-muted' }, '「重新生成」会按当前文字提交一次新的生成（产生一次费用）；「仅保存」不生成。留空保存则恢复自动渲染，修改不会改动拆解结果。')
          ) : null
        ) : null,
        err ? h('div', { className: 'adp-result-error' }, err) : null,
        run.last_edit_error ? h('div', { className: 'adp-result-error', style: { color: '#C99B54' } }, '上次单镜编辑失败：' + String(run.last_edit_error).slice(0, 300) + '（原成片未受影响）') : null,
        editOpen ? h('div', { className: 'adp-drawer-backdrop', onClick: () => setEditOpen(false) },
          h('div', { className: 'adp-drawer', role: 'dialog', 'aria-modal': 'true', 'aria-label': '修改生成参数', onClick: (e) => e.stopPropagation() },
            h('div', { className: 'adp-drawer-head' },
              h('div', null, h('div', { className: 'adp-h2' }, '修改生成参数'), h('div', { className: 'adp-small adp-muted' }, '只改生成设置，生成一个新版本。')),
              h('button', { className: 'adp-icon-btn', onClick: () => setEditOpen(false), title: '关闭' }, h(Glyph, { name: 'close' }))
            ),
            h('div', { className: 'adp-drawer-body' },
              h(Field, { label: '比例' }, h('select', { className: 'adp-select', value: edit.aspect, onChange: (e) => setEdit(Object.assign({}, edit, { aspect: e.currentTarget.value })) }, aspectOptions.map((x) => h('option', { key: x, value: x }, x)))),
              h(Field, { label: '清晰度' }, h('select', { className: 'adp-select', value: edit.resolution, onChange: (e) => setEdit(Object.assign({}, edit, { resolution: e.currentTarget.value })) }, resolutionOptions.map((x) => h('option', { key: x, value: x }, x)))),
              h(Field, { label: '时长（秒）' }, h('select', { className: 'adp-select', value: edit.duration, onChange: (e) => setEdit(Object.assign({}, edit, { duration: Number(e.currentTarget.value) })) }, durationOptions.map((x) => h('option', { key: x, value: x }, x + 's')))),
              h('div', { className: 'adp-side-note' }, editDirty ? '参数已修改，应用后会生成新版本。' : '参数没有变化，按钮不可用。')
            ),
            h('div', { className: 'adp-drawer-foot' },
              h('button', { className: 'adp-btn ghost', onClick: () => setEditOpen(false) }, '取消'),
              h('button', { className: 'adp-btn primary', onClick: applyEdit, disabled: !editDirty || busy === 'edit', title: editDirty ? '应用修改并生成新版本' : '参数没有变化' }, busy === 'edit' ? '提交中…' : '应用并重生成')
            )
          )
        ) : null
      )
    }

    function RecreateTab({ models, onStarted, personas, onRefreshPersonas }) {
      const [refAsset, setRefAsset] = useState(null)
      const [products, setProducts] = useState([])
      const [brief, setBrief] = useState('')
      const [advanced, setAdvanced] = useState({ generation_mode: 'fast', duration: 12, aspect: '9:16', resolution: '720p', model: '' })
      const [replaceScope, setReplaceScope] = useState('both')
      const [personScope, setPersonScope] = useState('main')
      const [audioMode, setAudioMode] = useState('regenerate')
      const preserveAllowed = replaceScope === 'person'
      useEffect(() => { if (!preserveAllowed && audioMode === 'preserve') setAudioMode('regenerate') }, [preserveAllowed, audioMode])
      const [touched, setTouched] = useState({})
      const [detected, setDetected] = useState(() => detectVideoParams(''))
      const [preview, setPreview] = useState(null)
      const [persona, setPersona] = useState({ gender: 'any', age: 'youth', body_type: 'standard', ethnicity: 'asian' })
      const [personaEnabled, setPersonaEnabled] = useState(false)
      const [personaId, setPersonaId] = useState('')
      const [busy, setBusy] = useState(false)
      const [personaBusy, setPersonaBusy] = useState(false)
      const [err, setErr] = useState('')
      const usableModels = (models || []).filter((m) => m.available && m.enabled !== false)
      const hasRealModel = usableModels.length > 0
      const selectedModel = (models || []).find((m) => m.id === advanced.model)
      const imageOnly = Boolean(selectedModel && !(selectedModel.capabilities || []).includes('text_to_video'))
      useEffect(() => {
        setAdvanced((prev) => {
          const usable = (models || []).filter((m) => m.available && m.enabled !== false)
          if (prev.model && usable.some((m) => m.id === prev.model)) return prev
          const pick = defaultModelId(models, true)
          return pick ? Object.assign({}, prev, { model: pick }) : prev
        })
      }, [models])
      const selectedPersona = (personas || []).find((p) => p.id === personaId)
      useEffect(() => { setDetected(detectVideoParams(brief)) }, [brief])
      const changeAdvanced = (next) => {
        const changed = {}
        for (const key of ['aspect', 'duration', 'resolution', 'generation_mode', 'subtitle']) {
          if (next[key] !== advanced[key]) changed[key] = true
        }
        if (Object.keys(changed).length) setTouched((prev) => Object.assign({}, prev, changed))
        setAdvanced(next)
      }
      // The brief wins: every parameter it names replaces the control value, and
      // the list below says exactly what will change before the run starts.
      const overrides = []
      if (detected.aspect && detected.aspect !== advanced.aspect) overrides.push('比例 ' + detected.aspect + '（控件 ' + advanced.aspect + '）')
      if (detected.duration && Number(detected.duration) !== Number(advanced.duration)) overrides.push('时长 ' + detected.duration + 's（控件 ' + advanced.duration + 's）')
      if (detected.resolution && detected.resolution !== advanced.resolution) overrides.push('清晰度 ' + detected.resolution + '（控件 ' + advanced.resolution + '）')
      if (detected.mode && detected.mode !== advanced.generation_mode) overrides.push('模式 精细（控件 快速）')
      if (detected.subtitle && detected.subtitle !== (advanced.subtitle || 'off')) overrides.push('字幕 ' + subtitleLabel(detected.subtitle) + '（控件 ' + subtitleLabel(advanced.subtitle) + '）')
      const savePersona = async () => {
        setPersonaBusy(true); setErr('')
        try {
          const created = await api('/personas', { method: 'POST', body: Object.assign({ name: '模特 ' + ((personas || []).length + 1), type: 'ai', consent: { confirmed: true, note: '运营创建' } }, persona) })
          setPersonaId(created.persona.id)
          onRefreshPersonas && await onRefreshPersonas()
        } catch (e) { setErr(String(e.message || e)) } finally { setPersonaBusy(false) }
      }
      const start = async () => {
        if (!refAsset) { setErr('请先上传参考视频'); return }
        if (imageOnly && !products.length) { setErr('当前模型是图生视频，请先上传至少一张商品图'); return }
        setBusy(true); setErr('')
        try {
          let smart = null
          try { smart = await parseIntentWithDsh(brief) } catch { smart = null }
          const next = Object.assign(detectVideoParams(brief))
          if (smart) {
            if (smart.aspect) next.aspect = smart.aspect
            if (smart.duration) next.duration = smart.duration
            if (smart.resolution) next.resolution = smart.resolution
            if (smart.mode) next.mode = smart.mode
            if (smart.subtitle) next.subtitle = smart.subtitle
            if (smart.vendor) next.vendor = smart.vendor
          }
          setDetected(next)
          const merged = Object.assign({}, advanced)
          if (next.aspect) merged.aspect = next.aspect
          if (next.duration) merged.duration = next.duration
          if (next.resolution) merged.resolution = next.resolution
          if (next.mode) merged.generation_mode = next.mode
          if (next.subtitle) merged.subtitle = next.subtitle
          const vendorModel = modelForVendor(next.vendor, models)
          if (vendorModel) merged.model = vendorModel
          const personaPayload = personaEnabled ? { persona, persona_map: personaId ? { A: personaId, B: personaId } : {} } : {}
          const data = await api('/runs', { method: 'POST', body: {
            scenario: 'viral-remake',
            inputs: { reference_asset_id: refAsset.id, product_asset_ids: products.map(p => p.id), brief },
            advanced: Object.assign({}, merged, { model: 'auto', remake_mode: 'auto', replace_scope: replaceScope, person_scope: personScope, audio_mode: audioMode }, personaPayload),
          } })
          onStarted(data.run)
          // A submitted remake is done: clear the form so the next visit starts empty.
          setBrief(''); setRefAsset(null); setProducts([]); setPreview(null)
          setPersonaEnabled(false); setPersonaId('')
          setDetected(detectVideoParams('')); setTouched({})
        } catch (e) { setErr(String(e.message || e)) } finally { setBusy(false) }
      }
      return h('div', { className: 'adp-page' },
        h('div', { className: 'adp-page-head' },
          h('div', null,
            h('div', { className: 'adp-eyebrow' }, 'SCENE 01 / VIRAL REMAKE'),
            h('h1', { className: 'adp-title' }, '爆款复刻')
          ),
          h('div', { className: 'adp-page-meta' },
            h(Badge, { status: hasRealModel ? 'ok' : 'bad' }, hasRealModel ? '模型已就绪' : '未配置模型'),
            h('span', null, '≤30s 参考片')
          )
        ),
        h('div', { className: 'adp-panel' },
          h('div', { className: 'adp-panel-grid' },
            h('section', { className: 'adp-asset-col' },
              h('div', { className: 'adp-section-head' },
                h('span', { className: 'adp-step' }, '01'),
                h('span', { className: 'adp-section-title' }, '素材'),
                h('span', { className: 'adp-section-note' }, '参考片决定结构')
              ),
              h('div', { className: 'adp-label' }, h('span', null, '参考视频'), h('span', { className: 'count' }, '必填')),
              h(DropVideo, { asset: refAsset, onAsset: setRefAsset, onPreview: setPreview }),
              h('div', { className: 'adp-label', style: { marginTop: 16 } },
                h('span', null, '商品图'),
                h('span', { className: 'count' }, (products.length || 0) + ' / 9')
              ),
              h(MediaGrid, { assets: products, onAdd: (list) => setProducts(prev => prev.concat(list).slice(0, 9)), onRemove: (id) => setProducts(prev => prev.filter(x => x.id !== id)), onPreview: setPreview }),
              h('div', { className: 'adp-hint' }, '可上传多张：正面、包装、细节、使用场景。第一张会作为主商品参考。'),
              h('div', { className: 'adp-asset-foot' },
                h('b', null, '素材建议'),
                h('div', null, '参考片：一条完整片子，不要混剪。'),
                h('div', null, '商品图：正面 + 包装 + 细节；没有图也可以先用文字描述。')
              )
            ),
            h('section', { className: 'adp-form-col' },
              h('div', { className: 'adp-section-head' },
                h('span', { className: 'adp-step' }, '02'),
                h('span', { className: 'adp-section-title' }, '创作需求'),
                h('span', { className: 'adp-section-note' }, '不用写 prompt')
              ),
              h('div', { className: 'adp-brief' },
                h('div', { className: 'adp-brief-head' },
                  h('b', null, '需求描述'),
                  h('span', null, brief.length + ' / 2000')
                ),
                h('textarea', {
                  className: 'adp-brief-input', value: brief, maxLength: 2000, rows: 4,
                  placeholder: '例如：产品活动价 19.9，卖点是不油腻、追剧零食；保留原片的比价和抢购动作，台词更生活化。',
                  onChange: (e) => setBrief(e.currentTarget.value),
                  onKeyDown: (e) => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); start() } }
                }),
                h('div', { className: 'adp-brief-foot' },
                  h('span', null, '写产品、卖点、价格、想保留/想改的地方；要原样念的台词用「」括起来。'),
                  h('div', { className: 'adp-row', style: { gap: 8 } },
                    h('span', { className: 'adp-key' }, '⌘ ↵ 开始')
                  )
                )
              ),
              h('div', { className: 'adp-section-head' },
                h('span', { className: 'adp-step' }, '03'),
                h('span', { className: 'adp-section-title' }, '生成设置')
              ),
              h(AdvancedRow, { value: advanced, onChange: changeAdvanced, models, needsDialogue: true, autoModel: true, autoTiming: true, timingNote: refAsset && refAsset.duration_s ? '跟随参考片 · ' + Number(refAsset.duration_s).toFixed(1) + 's' : '自动解析参考片', aspectNote: refAsset && refAsset.width && refAsset.height ? '跟随参考片 · ' + (refAsset.height > refAsset.width * 1.15 ? '9:16' : refAsset.width > refAsset.height * 1.15 ? '16:9' : '1:1') : '自动解析参考片' }),
              h('div', { className: 'adp-field-grid g3' },
                h(FormSelect, { label: '替换内容', value: replaceScope, onChange: setReplaceScope, options: [{ value: 'both', label: '人物 + 商品' }, { value: 'product', label: '只换商品' }, { value: 'person', label: '只换人物' }] }),
                h(FormSelect, { label: '人物范围', value: personScope, onChange: setPersonScope, options: [{ value: 'main', label: '只换主角' }, { value: 'all', label: '全部人物' }] }),
                h(FormSelect, { label: '声音', value: audioMode, onChange: setAudioMode, options: preserveAllowed ? [{ value: 'regenerate', label: '按新台词生成' }, { value: 'preserve', label: '保留原声' }] : [{ value: 'regenerate', label: '按新台词生成' }] })
              ),
              h('div', { className: 'adp-hint' }, preserveAllowed ? '只换人物时可以保留原声；换商品会自动改为按新台词生成，避免旧产品名/旧价格残留在口播里。' : '换商品必须按新台词生成：参考片会去音轨后交给 H3，避免旧产品名/旧价格叠加。'),
              imageOnly ? h('div', { className: 'adp-hint' }, '当前模型是图生视频：需要至少一张商品图；无原生音频。') : null,
              overrides.length ? h('div', { className: 'adp-conflict', style: { margin: '7px 0 0' } }, h('b', null, '描述优先'), overrides.join('；')) : null,
              h('div', { className: 'adp-section-head' },
                h('span', { className: 'adp-step' }, '04'),
                h('span', { className: 'adp-section-title' }, '模特'),
                h('span', { className: 'adp-section-note' }, '先定人，再定片')
              ),
              h('div', { className: 'adp-persona-inline' },
                h('label', { className: 'adp-check', style: { marginTop: 0 } },
                  h('input', { type: 'checkbox', checked: personaEnabled, onChange: (e) => { const on = e.currentTarget.checked; setPersonaEnabled(on); if (!on) setPersonaId('') } }),
                  '本次使用模特设定'
                ),
                h('div', { className: 'adp-persona-status' },
                  h(Badge, { status: personaEnabled ? (personaId ? 'ok' : '') : '' }, personaEnabled ? (personaId ? '已选：' + (selectedPersona ? selectedPersona.name : '已保存模特') : '本次自定义') : '本次不使用模特'),
                  h('span', { className: 'adp-small adp-muted' }, personaEnabled ? (personaId ? '下方字段已带入；修改任意字段会切换为本次自定义，不会改动已保存模特。' : '以下字段只影响本次生成，不会修改模特库。') : '原片没有人物、或不需要改人物时保持关闭；不会把模特写进生成要求。')
                ),
                h('div', { className: personaEnabled ? '' : 'adp-persona-off' },
                  h('div', { className: 'adp-persona-source' },
                    h('div', { className: 'adp-field-label' }, '已保存模特（可选）'),
                    h('select', { className: 'adp-select', value: personaId, disabled: !personaEnabled, onChange: (e) => {
                      const id = e.currentTarget.value
                      setPersonaId(id)
                      const found = (personas || []).find(p => p.id === id)
                      if (found) { setPersona({ gender: found.gender || 'any', age: found.age || 'youth', body_type: found.body_type || 'standard', ethnicity: found.ethnicity || 'asian' }); setPersonaEnabled(true) }
                    } },
                      h('option', { value: '' }, '本次自定义'),
                      (personas || []).map(p => h('option', { key: p.id, value: p.id }, p.name + ' · ' + (p.gender === 'female' ? '女' : p.gender === 'male' ? '男' : '不限') + ' · ' + (p.age || '')))
                    )
                  ),
                  h(PersonaFields, { value: persona, onChange: (v) => { setPersonaId(''); setPersona(v) } })
                ),
                h('div', { className: 'adp-persona-actions' },
                  h('button', { className: 'adp-btn ghost', onClick: savePersona, disabled: !personaEnabled || personaBusy }, personaBusy ? '保存中…' : (personaId ? '另存为副本' : '另存为模特')),
                  h('span', { className: 'adp-hint' }, personaEnabled ? (personaId ? '不会覆盖当前选中的已保存模特' : '保存后可在模特库复用') : '关闭时不会影响原片人物或生成 prompt')
                )
              ),
              h('div', { className: 'adp-actionbar' },
                h('div', { className: 'adp-action-note' },
                  !refAsset ? h('span', { style: { color: '#C99B54' } }, '先上传参考视频。') : (hasRealModel ? '将使用已配置的模型；生成通常需要几分钟。' : '还没有可用的视频模型，先去「设置」里配置厂商 key。'),
                  h('br'),
                  '开始后可在结果页看分镜、派生新版本。'
                ),
                h('div', { className: 'adp-grow' }),
                h('button', { className: 'adp-primary', onClick: start, disabled: busy || !refAsset },
                  busy ? '正在启动…' : '开始复刻',
                  h('span', { className: 'arrow' }, '→')
                )
              ),
              err ? h('div', { className: 'adp-error', style: { marginTop: 10 } }, err) : null
            )
          )
        ),
        preview ? h(PreviewModal, { asset: preview, onClose: () => setPreview(null) }) : null
      )
    }

    const CHAT_ASPECTS = ['9:16', '16:9', '1:1', '4:3', '3:4', '21:9']
    // 引擎只支持这三档（image_params.size_for），其它值会被默默当成 2K。
    const CHAT_AREAS = ['1K', '2K', '4K']
    const CHAT_AREA_SIZES = { '1K': 1, '2K': 2, '4K': 4 }

    const normalizeArea = (value) => {
      const raw = String(value || '').trim().toUpperCase()
      if (CHAT_AREAS.includes(raw)) return raw
      const size = Number(raw.replace(/[^\d.]/g, ''))
      if (!Number.isFinite(size) || size <= 0) return '2K'
      // 向上取最近的可用档：1.5k→2K、3k→4K、4.5k→4K。
      return CHAT_AREAS.find((candidate) => CHAT_AREA_SIZES[candidate] >= size) || '4K'
    }

    const chatNorm = (value) => String(value || '')
      .replace(/[\s\u3000]+/g, '')
      .replace(/[，。！？、,.!?~～…「」"'“”]/g, '')
      .toLowerCase()

    // "生成吧 / 就按这个来 / 确认" 等确认语只在存在待生成卡片时生效。
    const isConfirmIntent = (text) => {
      const t = chatNorm(text).replace(/(吧|了|啊|呀|哦|呢|啦|来|嘛)+$/, '')
      if (!t || t.length > 12) return false
      return /^(生成|开始|开始生成|确认|确认生成|就这个|就它|就按这个|按这个生成|按这个来|可以|行|好的|好|执行|go|ok|okay)$/.test(t)
    }

    const proposalSpec = (p) => p.kind === 'image'
      ? p.aspect + ' · ' + p.area
      : p.aspect + ' · ' + p.duration + ' 秒 · ' + p.resolution

    // 改比例/尺寸/时长这类纯参数调整走本地规则，立即生成新卡片，不再问模型。
    const patchProposal = (text, base) => {
      if (!base) return null
      const t = chatNorm(text)
      const next = Object.assign({}, base)
      const notes = []

      // 同时要改内容（加 logo / 换风格 / 改文案）时交给模型重写 prompt，这里只处理纯参数。
      const wording = t.replace(/换成|改成|改为|变成|做成|转成/g, '')
      if (/加|增|去掉|删|替换|风格|文案|标题|品牌|logo|slogan|字体|色调|颜色|氛围|光线|灯光|场景|背景|人物|模特|产品|构图/.test(wording)) return null

      let kind = base.kind
      if (/改成视频|换成视频|改为视频|变成视频|做成视频|转成视频/.test(t)) kind = 'video'
      else if (/改成图片|换成图片|改为图片|变成图片|改成海报|换成海报|改为海报|做成图片/.test(t)) kind = 'image'
      const kindChanged = kind !== base.kind

      let aspect = ''
      if (/21:9|超宽/.test(t)) aspect = '21:9'
      else if (/16:9|横屏|横版|横向|横图|宽屏/.test(t)) aspect = '16:9'
      else if (/9:16|竖屏|竖版|竖向|竖图/.test(t)) aspect = '9:16'
      else if (/4:3/.test(t)) aspect = '4:3'
      else if (/3:4/.test(t)) aspect = '3:4'
      else if (/1:1|方形|正方形|方图/.test(t)) aspect = '1:1'

      let resolution = ''
      if (/1080|全高清/.test(t)) resolution = '1080p'
      else if (/720/.test(t)) resolution = '720p'
      else if (/480/.test(t)) resolution = '480p'

      let area = ''
      const sizeMatch = t.match(/(\d+(?:\.\d+)?)\s*k(?![a-z])/)
      if (sizeMatch) area = normalizeArea(sizeMatch[1] + 'K')

      const seconds = t.match(/(\d+(?:\.\d+)?)(?:秒|s)/)
      const duration = seconds ? Math.max(1, Math.min(30, Math.round(Number(seconds[1])))) : 0

      if (aspect && aspect !== next.aspect) { next.aspect = aspect; notes.push('比例 → ' + aspect) }
      if (kindChanged) {
        next.kind = kind
        notes.push('类型 → ' + (kind === 'image' ? '图片' : '视频'))
        if (!aspect) next.aspect = kind === 'video' ? '9:16' : '1:1'
      }
      if (next.kind === 'video') {
        if (resolution && resolution !== next.resolution) { next.resolution = resolution; notes.push('清晰度 → ' + resolution) }
        if (duration && duration !== next.duration) { next.duration = duration; notes.push('时长 → ' + duration + ' 秒') }
      } else if (area && area !== next.area) {
        next.area = area
        const asked = sizeMatch ? Number(sizeMatch[1]) : 0
        notes.push('尺寸档位 → ' + area + (asked > 4 ? '（最高支持 4K）' : ''))
      }

      if (!notes.length) return null
      if (next.kind === 'image') {
        delete next.duration
        delete next.resolution
        if (!CHAT_ASPECTS.includes(next.aspect)) next.aspect = '1:1'
        if (!next.area) next.area = '2K'
      } else {
        delete next.area
        if (!CHAT_ASPECTS.includes(next.aspect)) next.aspect = '9:16'
        if (!next.duration) next.duration = 8
        if (!next.resolution) next.resolution = '720p'
      }
      return { proposal: next, notes }
    }

    // 自由创作对话保存在本机（浏览器侧），历史入口读的就是这份。
    const CONVERSATIONS_KEY = 'adclip.freecreate.conversations.v1'

    const loadConversations = () => {
      try {
        const raw = window.localStorage.getItem(CONVERSATIONS_KEY)
        const value = JSON.parse(raw || '[]')
        return Array.isArray(value)
          ? value.filter((entry) => entry && entry.id && Array.isArray(entry.thread))
          : []
      } catch { return [] }
    }

    const saveConversations = (list) => {
      try { window.localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(list.slice(0, 40))) } catch { /* 存储不可用时只丢历史，不影响对话 */ }
    }

    function TextTab({ dsh, textModels, onStarted, onRefreshAssets }) {
      const [conversations, setConversations] = useState(() => loadConversations())
      // 刷新后回到上次那段对话，而不是一片空白。
      const [thread, setThread] = useState(() => (conversations[0] && conversations[0].thread) || [])
      const [pending, setPending] = useState(null)
      const [composer, setComposer] = useState('')
      const [images, setImages] = useState([])
      const [textModel, setTextModel] = useState(null)
      const [busy, setBusy] = useState(false)
      const [err, setErr] = useState('')
      const [convId, setConvId] = useState(() => (conversations[0] && conversations[0].id) || 'c' + Date.now())
      const [showHistory, setShowHistory] = useState(false)
      const input = useRef(null)
      const scrollRef = useRef(null)
      const composerRef = useRef(null)
      const lastProposalRef = useRef(null)
      const selectedTextModel = textModel || defaultDshTextModel(dsh, textModels)
      const hasTextModel = Boolean(selectedTextModel)
      const locked = Boolean(pending)
      useEffect(() => {
        const el = scrollRef.current
        if (el) el.scrollTop = el.scrollHeight
      }, [thread, busy])
      // 对话随时写回本机，刷新或切回来还能恢复。
      useEffect(() => {
        if (!thread.length) return
        const first = thread.find((message) => message.role === 'user')
        const title = String((first && first.text) || '新对话').replace(/\s+/g, ' ').slice(0, 26)
        const now = Date.now()
        setConversations((prev) => {
          const exists = prev.find((entry) => entry.id === convId)
          const next = [{ id: convId, title, createdAt: (exists && exists.createdAt) || now, updatedAt: now, thread }]
            .concat(prev.filter((entry) => entry.id !== convId))
          saveConversations(next)
          return next
        })
      }, [thread, convId])

      const systemPrompt = [
        '你是 AdClip 自由创作助手。先判断用户这句话的意图，再决定要不要出生成确认卡片。',
        '只输出一个 JSON 对象，不要 markdown、不要解释 JSON：',
        '{"intent":"chat|revise|create|cancel","reply":"给用户看的中文回复","kind":"image|video","prompt":"完整画面描述","patch":{"aspect":"1:1","area":"2K","duration":8,"resolution":"720p"}}',
        '意图规则：',
        '- chat：普通聊天、问候、提问、讨论方案、改文案建议、信息不足。reply 正常回答，不要提卡片。',
        '- revise：在改上一版提案。只改参数就填 patch（aspect 取 9:16|16:9|1:1|4:3|3:4|21:9；area 取 1K|2K|4K；duration 1-30；resolution 取 480p|720p|1080p；kind 取 image|video）。改画面内容就重写 prompt：保留上一版主体描写，只改用户要求的部分。',
        '- create：用户要一张新图/新视频。prompt 必须完整，kind 必须给。',
        '- cancel：用户说算了/不要了/不做了/取消。',
        '只有 revise/create 会让界面出现确认卡片；卡片由用户点“生成”才开始，所以 reply 不能写“已生成/已经生成好了/已做好”。',
        '用户没提到的参数不要放进 patch，不要自己发明参数；不确定就用 chat 并反问。',
        '例外：用户给出的参数超出支持范围时（如 4.5K、99 秒），直接取最接近的合法值写进 patch，并在 reply 里用一句话说明取了哪个值；不要反问后不出卡片。',
        '默认值：图片 1:1、2K；视频 9:16、8 秒、720p。图片 area 只支持 1K / 2K / 4K。',
      ].join('\n')

      // 模型给的 patch 不可信，逐字段校验后只保留能用的。
      const sanitizePatch = (value) => {
        const patch = {}
        if (!value || typeof value !== 'object') return patch
        const aspect = String(value.aspect || '').trim()
        if (CHAT_ASPECTS.includes(aspect)) patch.aspect = aspect
        const area = String(value.area || '').trim()
        if (area) patch.area = normalizeArea(area)
        const duration = Number(value.duration)
        if (Number.isFinite(duration) && duration >= 1 && duration <= 30) patch.duration = Math.round(duration)
        const resolution = String(value.resolution || '').trim().toLowerCase()
        if (['480p', '720p', '1080p'].includes(resolution)) patch.resolution = resolution
        const kind = String(value.kind || '').trim()
        if (['image', 'video'].includes(kind)) patch.kind = kind
        return patch
      }

      // 合并后补齐该类任务需要、但对方没给的字段。
      const mergeProposal = (base, patch) => {
        const next = Object.assign({}, base || {}, patch || {})
        if (next.kind === 'video') {
          delete next.area
          if (!CHAT_ASPECTS.includes(next.aspect)) next.aspect = '9:16'
          if (!next.duration) next.duration = 8
          if (!next.resolution) next.resolution = '720p'
        } else {
          next.kind = 'image'
          delete next.duration
          delete next.resolution
          if (!CHAT_ASPECTS.includes(next.aspect)) next.aspect = '1:1'
          if (!next.area) next.area = '2K'
        }
        return next
      }

      const parseReply = (raw) => {
        const text = String(raw || '').trim()
        if (!text) return { intent: 'chat', reply: '模型没有返回内容。', kind: '', prompt: '', patch: {} }
        const start = text.indexOf('{')
        const end = text.lastIndexOf('}')
        if (start >= 0 && end > start) {
          try {
            const value = JSON.parse(text.slice(start, end + 1))
            const intents = ['chat', 'revise', 'create', 'cancel']
            const kind = ['image', 'video'].includes(String(value.kind))
              ? String(value.kind)
              : (['image', 'video'].includes(String(value.action)) ? String(value.action) : '')
            // 兼容旧字段 action=image/video 的回复。
            const intent = intents.includes(String(value.intent))
              ? String(value.intent)
              : (kind ? 'create' : 'chat')
            const reply = String(value.reply || '').trim()
            const prompt = String(value.prompt || '').trim()
            return {
              intent,
              kind,
              prompt,
              patch: sanitizePatch(value.patch),
              reply: reply || (prompt ? '我整理好了，确认后点生成。' : '请再具体描述一下你想做的内容。'),
            }
          } catch { /* fall through to plain text */ }
        }
        return { intent: 'chat', reply: text, kind: '', prompt: '', patch: {} }
      }

      const upload = async (event) => {
        const picked = Array.from(event.currentTarget.files || [])
        event.currentTarget.value = ''
        if (!picked.length) return
        setBusy(true); setErr('')
        try {
          const next = images.slice()
          for (const file of picked) {
            if (!file.type.startsWith('image/')) { setErr('自由创作只接收图片附件'); continue }
            if (next.length >= 4) break
            next.push(await uploadFile(file, 'image'))
          }
          setImages(next)
          onRefreshAssets && await onRefreshAssets()
        } catch (e) { setErr(String(e.message || e)) } finally { setBusy(false) }
      }
      const removeImage = (id) => setImages((prev) => prev.filter((x) => x.id !== id))

      const pushMessage = (role, text, source) => setThread((prev) => prev.concat([
        source ? { role, text, source } : { role, text },
      ]))

      const generate = async (proposal) => {
        if (!proposal || !proposal.prompt) { setErr('生成内容为空'); return false }
        setBusy(true); setErr('')
        try {
          if (proposal.kind === 'image') {
            const data = await api('/images', { method: 'POST', body: {
              prompt: proposal.prompt,
              aspect: proposal.aspect || '1:1',
              area: proposal.area || '2K',
              reference_asset_id: images[0] ? images[0].id : '',
            } })
            onStarted(data.run)
          } else {
            const data = await api('/runs', { method: 'POST', body: {
              scenario: 'text-to-video',
              inputs: { brief: proposal.prompt, reference_image_asset_id: images[0] ? images[0].id : null },
              advanced: {
                aspect: proposal.aspect || '9:16',
                duration: proposal.duration || 8,
                resolution: proposal.resolution || '720p',
                model: 'auto',
                ...(selectedTextModel && selectedTextModel.provider === 'ark'
                  ? { text_model: { provider: 'ark', model: selectedTextModel.model } }
                  : {}),
              },
            } })
            onStarted(data.run)
          }
          return true
        } catch (e) { setErr(String(e.message || e)); return false } finally { setBusy(false) }
      }

      const confirmPending = async () => {
        const proposal = pending
        if (!proposal) return
        setPending(null)
        const ok = await generate(proposal)
        if (ok) {
          lastProposalRef.current = proposal
          pushMessage('system', '已提交生成：' + (proposal.kind === 'image' ? '图片' : '视频') + ' · ' + proposalSpec(proposal))
        } else {
          // 失败时把卡片放回来，别让用户丢掉已确认的文案和参数。
          setPending(proposal)
        }
      }

      const cancelPending = () => {
        const proposal = pending
        setPending(null)
        if (proposal) pushMessage('system', '已取消这次生成（' + (proposal.kind === 'image' ? '图片' : '视频') + ' · ' + proposalSpec(proposal) + '）')
      }

      const newChat = () => {
        setThread([])
        setPending(null)
        setComposer('')
        setErr('')
        setShowHistory(false)
        lastProposalRef.current = null
        setConvId('c' + Date.now())
      }

      const openConversation = (entry) => {
        setThread(entry.thread || [])
        setPending(null)
        setComposer('')
        setErr('')
        setShowHistory(false)
        lastProposalRef.current = null
        setConvId(entry.id)
      }

      const removeConversation = (id) => {
        setConversations((prev) => {
          const next = prev.filter((entry) => entry.id !== id)
          saveConversations(next)
          return next
        })
      }

      const send = async () => {
        const text = composer.trim()
        if (!text) { setErr('先输入一句话'); return }
        if (pending) { setErr('先确认或取消输入框上方的生成卡片'); return }
        setErr('')
        const previous = lastProposalRef.current

        // “生成吧/确认”直接回到上一版卡片，不用再问模型。
        if (previous && isConfirmIntent(text)) {
          setComposer('')
          pushMessage('user', text)
          setPending(Object.assign({}, previous))
          return
        }
        if (!hasTextModel) { setErr('先在 DSH 配置一个文本模型'); return }
        const nextThread = thread.concat([{ role: 'user', text }])
        setThread(nextThread)
        setComposer('')
        setBusy(true); setErr('')
        try {
          // 卡片不进聊天流。上一版提案只能放 system：DSH 的 llm 派发会读 assistant
          // 消息的 source.replayState，自己拼的 assistant 消息会直接报错。
          const system = previous
            ? systemPrompt + '\n当前已有一版提案，用户可能是在它基础上继续：类型='
              + (previous.kind === 'image' ? '图片' : '视频') + '；规格=' + proposalSpec(previous)
              + '；prompt=' + String(previous.prompt || '').slice(0, 900)
            : systemPrompt
          // DSH 的消息契约：assistant 消息必须带 source，否则 forAdapter 读
          // source.replayState 时抛 TypeError。历史消息缺 source 时用当前模型兜底。
          const fallbackSource = {
            kind: 'model',
            provider: String((selectedTextModel && selectedTextModel.provider) || ''),
            model: String((selectedTextModel && selectedTextModel.model) || ''),
          }
          const messages = nextThread
            .filter((message) => message.role === 'user' || message.role === 'assistant')
            .slice(-10)
            .map((message) => {
              const entry = { role: message.role, content: [{ type: 'text', text: String(message.text || '').slice(0, 1200) }] }
              if (message.role === 'assistant') {
                const source = message.source || fallbackSource
                entry.source = {
                  kind: 'model',
                  provider: source.provider || fallbackSource.provider,
                  model: source.model || fallbackSource.model,
                }
              }
              return entry
            })
          const arkSelected = Boolean(selectedTextModel && selectedTextModel.provider === 'ark')
          const data = arkSelected
            ? await api('/text/chat', { method: 'POST', body: {
                system,
                messages,
                maxTokens: 900,
                provider: 'ark',
                model: selectedTextModel.model,
              } })
            : await api('/dsh/chat', { method: 'POST', body: {
                system,
                messages,
                maxTokens: 900,
                provider: selectedTextModel && selectedTextModel.provider,
                model: selectedTextModel && selectedTextModel.model,
              } })
          const raw = String((data.dsh && data.dsh.text) || data.text || '')
          const replySource = {
            kind: 'model',
            provider: String((data.dsh && data.dsh.provider) || data.provider || (selectedTextModel && selectedTextModel.provider) || ''),
            model: String((data.dsh && data.dsh.model) || data.model || (selectedTextModel && selectedTextModel.model) || ''),
          }
          const decision = parseReply(raw)
          let reply = decision.reply
          let next = null

          if (decision.intent === 'cancel') {
            setPending(null)
            lastProposalRef.current = null
            pushMessage('system', '已取消这次生成' + (previous
              ? '（' + (previous.kind === 'image' ? '图片' : '视频') + ' · ' + proposalSpec(previous) + '）'
              : ''))
            pushMessage('assistant', reply, replySource)
            return
          }

          if (decision.intent === 'create') {
            if (decision.prompt) {
              next = mergeProposal({ prompt: decision.prompt, kind: decision.kind || 'image' }, decision.patch)
            }
          } else if (decision.intent === 'revise') {
            const prompt = decision.prompt || (previous && previous.prompt) || ''
            if (prompt) {
              next = mergeProposal(Object.assign({}, previous || { kind: decision.kind || 'image' }, { prompt }), decision.patch)
            }
          }

          if (next) {
            lastProposalRef.current = next
            setPending(next)
            // 卡片只是待确认；模型习惯说“已生成”，这里改成准备完成的措辞。
            reply = reply.replace(/已(?:经)?(?:为你|帮你|给你)?(?:生成|做好|完成|画好|出好)/g, '已准备好')
            if (!/卡片|确认|点(?:击|一下|上方|上面)/.test(reply)) {
              reply = reply + '（点输入框上方的按钮才会真正开始生成）'
            }
          } else if (previous && /确认后点生成|点.{0,6}生成.{0,4}即可|已准备好确认卡片|卡片已就绪/.test(reply)) {
            // 模型说“确认后点生成”却没给可用提案：把上一版挂回去，不留空承诺。
            const pinned = mergeProposal(previous, decision.patch)
            lastProposalRef.current = pinned
            setPending(pinned)
          }
          pushMessage('assistant', reply, replySource)
          if (/拼接|拼起来|拼成|接起来|合并|组合|连起来/.test(text)) {
            pushMessage('assistant', '拼接不在自由创作页处理；需要拼接时请通过 DSH 的拼接工具完成。', replySource)
          }
        } catch (e) {
          // 模型不可用时退回本地参数规则，至少纯参数修改仍然能用。
          const fallback = previous ? patchProposal(text, previous) : null
          if (fallback) {
            lastProposalRef.current = fallback.proposal
            setPending(fallback.proposal)
            pushMessage('system', '文本模型不可用，已按本地规则更新：' + fallback.notes.join('、'))
          } else {
            setErr(String(e.message || e))
          }
        } finally { setBusy(false) }
      }

      return h('div', { className: 'adp-page adp-chatpage' },
        h('div', { className: 'adp-chat-head' },
          h('div', { className: 'adp-chat-title' },
            h('div', { className: 'adp-eyebrow' }, 'FREE CREATE'),
            h('h1', { className: 'adp-title' }, '自由创作')
          ),
          h('div', { className: 'adp-chat-actions' },
            h('button', {
              className: 'adp-btn ghost',
              onClick: newChat,
              disabled: busy || (!thread.length && !pending),
              title: '新对话',
              'aria-label': '新对话',
            }, h(Glyph, { name: 'plus', size: 15 })),
            h('button', {
              className: 'adp-btn ghost',
              onClick: () => setShowHistory(true),
              title: conversations.length ? '历史对话（' + conversations.length + '）' : '历史对话',
              'aria-label': '历史对话',
            }, h(Glyph, { name: 'history', size: 15 }))
          )
        ),
        h('div', { className: 'adp-chat-main' },
          h('div', { className: 'adp-chat-scroll' + (thread.length ? '' : ' empty'), ref: scrollRef },
            thread.length
              ? thread.map((message, index) => h('div', {
                key: index,
                className: 'adp-msg' + (message.role === 'user' ? ' user' : '') + (message.role === 'system' ? ' sys' : ''),
              }, h('div', null, message.text)))
              : h('div', { className: 'adp-chat-empty' },
                h('div', { className: 'adp-chat-empty-mark' }, '✦'),
                h('h2', null, '今天想创作什么？'),
                h('p', null, '可以聊天、问方案；明确说“画一张…”或“做一条…”时，我才会给出生成提案。'),
                h('div', { className: 'adp-chat-suggestions' },
                  ['画一张咖啡海报', '做一条 8 秒产品视频', '帮我写个广告脚本'].map((item) => h('button', {
                    key: item,
                    className: 'adp-suggestion',
                    onClick: () => { setComposer(item); composerRef.current && composerRef.current.focus() },
                  }, item))
                )
              )
          ),
          pending ? h('div', { className: 'adp-confirm-dock' },
            h('div', { className: 'adp-confirm-card' },
              h('div', { className: 'adp-confirm-head' },
                h('span', { className: 'adp-confirm-tag' }, '等待确认 · ' + (pending.kind === 'image' ? '图片' : '视频')),
                h('b', null, proposalSpec(pending))
              ),
              h('div', { className: 'adp-confirm-brief' }, pending.prompt),
              h('div', { className: 'adp-confirm-actions' },
                h('button', { className: 'adp-btn ghost', onClick: cancelPending, disabled: busy }, '取消'),
                h('button', { className: 'adp-btn primary', onClick: confirmPending, disabled: busy },
                  busy ? '提交中…' : (pending.kind === 'image' ? '生成图片' : '生成视频'))
              )
            )
          ) : null,
          h('div', { className: 'adp-chat-composer' },
            h('div', { className: 'adp-composer adp-create-composer' },
              h('textarea', {
                ref: composerRef,
                className: 'adp-composer-input',
                value: composer,
                maxLength: 1000,
                disabled: locked,
                placeholder: locked
                  ? '先确认或取消输入框上方的生成卡片'
                  : '聊天、问方案，或明确说“画一张咖啡海报 / 做一条 8 秒咖啡视频”。',
                onChange: (e) => setComposer(e.currentTarget.value),
                onKeyDown: (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } },
              }),
              h('div', { className: 'adp-attachments' },
                images.map((file) => h('div', { key: file.id, className: 'adp-attach' },
                  h('img', { src: mediaUrl(file.path), alt: file.name }),
                  h('button', { className: 'adp-attach-remove', title: '移除', onClick: () => removeImage(file.id) }, '×'),
                  h('span', { className: 'adp-attach-kind' }, '参考图')
                )),
                h('button', { className: 'adp-attach-add', onClick: () => { if (!locked) input.current && input.current.click() }, title: '添加参考图，可多选，最多 4 张' },
                  h('b', null, '+'), h('span', null, '参考图'), h('small', null, '可多选')
                ),
                h('input', { ref: input, type: 'file', accept: 'image/*', multiple: true, onChange: upload, style: { display: 'none' } })
              ),
              h('div', { className: 'adp-composer-foot' },
                h('div', { className: 'adp-composer-left' },
                  h(TextModelSelect, { dsh, textModels, value: selectedTextModel, onChange: setTextModel }),
                  !hasTextModel ? h('span', { className: 'adp-hint' }, '未配置文本模型') : null
                ),
                h('div', { className: 'adp-composer-right' },
                  h('span', { className: 'adp-composer-count' }, composer.length + ' / 1000'),
                  h('button', { className: 'adp-send', onClick: send, disabled: busy || !hasTextModel || locked, title: locked ? '先确认或取消生成卡片' : '发送' }, busy ? '…' : '↑')
                )
              )
            )
          )
        ),
        err ? h('div', { className: 'adp-error' }, err) : null,
        showHistory ? h('div', { className: 'adp-modal-backdrop', onClick: () => setShowHistory(false) },
          h('div', { className: 'adp-modal adp-history-modal', role: 'dialog', 'aria-modal': 'true', 'aria-label': '历史对话', onClick: (e) => e.stopPropagation() },
            h('div', { className: 'adp-modal-head' },
              h('div', null,
                h('div', { className: 'adp-h2' }, '历史对话'),
                h('div', { className: 'adp-small adp-muted' }, '保存在本机，点一条就能接着聊。')
              ),
              h('button', { className: 'adp-icon-btn', onClick: () => setShowHistory(false), title: '关闭' }, h(Glyph, { name: 'close' }))
            ),
            h('div', { className: 'adp-modal-body' },
              conversations.length
                ? h('div', { className: 'adp-history-list' }, conversations.map((entry) => h('div', {
                  key: entry.id,
                  className: 'adp-history-row' + (entry.id === convId ? ' active' : ''),
                },
                  h('button', { className: 'adp-history-open', onClick: () => openConversation(entry) },
                    h('b', null, entry.title || '未命名对话'),
                    h('span', null, new Date(entry.updatedAt).toLocaleString() + ' · ' + entry.thread.length + ' 条')
                  ),
                  h('button', {
                    className: 'adp-icon-btn',
                    title: '删除这条对话',
                    onClick: () => removeConversation(entry.id),
                  }, h(Glyph, { name: 'close' }))
                )))
                : h('div', { className: 'adp-empty-state' },
                    h('b', null, '还没有历史对话'),
                    h('span', { className: 'adp-muted' }, '开始聊天后会自动保存在这里。')
                  )
            ),
            h('div', { className: 'adp-modal-foot' },
              h('button', { className: 'adp-btn ghost', onClick: () => setShowHistory(false) }, '关闭')
            )
          )
        ) : null
      )
    }

    function assetMeta(a) {
      const kind = { image: '图片', video: '视频', audio: '音频' }[a.kind] || a.kind || '文件'
      const facts = [kind]
      if (a.duration_s) facts.push(fmt(a.duration_s))
      else if (a.width && a.height) facts.push(a.width + '×' + a.height)
      return facts.join(' · ')
    }

    function statusStamp(status) {
      if (status === 'succeeded') return { label: '完成', tone: 'ok' }
      if (status === 'failed') return { label: '失败', tone: 'bad' }
      if (status === 'canceled') return { label: '取消', tone: 'muted' }
      if (status === 'running') return { label: '生成中', tone: 'warn' }
      return { label: '排队', tone: 'muted' }
    }

    function TaskCard({ run, onOpen, selected, onSelect, onRenamed }) {
      const [renaming, setRenaming] = useState(false)
      const [title, setTitle] = useState(run.title || '')
      const [busy, setBusy] = useState(false)
      useEffect(() => { setTitle(run.title || '') }, [run.title])
      const canSelect = run.status === 'succeeded'
      const stamp = statusStamp(run.status)
      const save = async () => {
        setBusy(true)
        try {
          const data = await api('/runs/' + run.id, { method: 'PATCH', body: { title: title.trim() } })
          const next = data.run.title
          setTitle(next)
          setRenaming(false)
          onRenamed && onRenamed(run.id, next)
        } catch (e) { window.alert(String(e.message || e)) } finally { setBusy(false) }
      }
      return h('div', { className: 'adp-run-card' + (selected ? ' selected' : ''), onClick: () => { if (!renaming) onOpen(run) } },
        h('div', { className: 'adp-task-head' },
          canSelect ? h('input', { type: 'checkbox', className: 'adp-task-check', checked: selected, onClick: (e) => e.stopPropagation(), onChange: () => onSelect(run.id) }) : h('span', { className: 'adp-task-check-spacer' }),
          renaming
            ? h('input', { className: 'adp-input adp-grow adp-task-title-input', value: title, autoFocus: true, onClick: (e) => e.stopPropagation(), onChange: (e) => setTitle(e.currentTarget.value), onKeyDown: (e) => { if (e.key === 'Enter') save(); if (e.key === 'Escape') setRenaming(false) } })
            : h('div', { className: 'adp-task-title', title: run.title || run.scenario }, run.title || run.scenario),
          renaming
            ? h('div', { className: 'adp-row', style: { gap: 2 } },
                h('button', { className: 'adp-task-save ok', onClick: (e) => { e.stopPropagation(); save() }, disabled: busy, title: '保存名称' }, busy ? '…' : h(Glyph, { name: 'check', size: 14 })),
                h('button', { className: 'adp-task-save', onClick: (e) => { e.stopPropagation(); setRenaming(false) }, title: '取消' }, h(Glyph, { name: 'close', size: 13 }))
              )
            : h('button', { className: 'adp-icon-btn adp-task-edit', title: '重命名', onClick: (e) => { e.stopPropagation(); setRenaming(true) } }, h(Glyph, { name: 'edit', size: 13 }))
        ),
        h('div', { className: 'adp-small adp-muted adp-task-scenario' }, (run.scenario === 'text-to-image' ? '文生图片' : run.scenario) + ' · ' + ((run.advanced && run.advanced.model) || 'auto')),
        h('div', { className: 'adp-small adp-faint adp-task-time' }, '创建 ' + fmtDateTime(run.created_at)),
        h('div', { className: 'adp-small adp-faint adp-task-time' }, '完成 ' + (run.finished_at ? fmtDateTime(run.finished_at) : '—') + ' · 耗时 ' + runDuration(run)),
        h('div', { className: 'adp-progress adp-task-progress' }, h('i', { style: { width: Math.round((run.progress || 0) * 100) + '%' } })),
        h('div', { className: 'adp-status-stamp ' + stamp.tone, title: '状态：' + stamp.label, 'aria-label': '状态：' + stamp.label },
          h('svg', { className: 'stamp-ring', viewBox: '0 0 44 44', 'aria-hidden': true },
            h('circle', { cx: 22, cy: 22, r: 21, fill: 'none', stroke: 'currentColor', strokeWidth: 1 }),
            h('circle', { cx: 22, cy: 22, r: 17, fill: 'none', stroke: 'currentColor', strokeWidth: 1, strokeDasharray: '2 3', opacity: 0.65 })
          ),
          h('b', null, stamp.label)
        )
      )
    }

    function AssetsTab({ onRefresh }) {
      const [page, setPage] = useState(1)
      const [pageSize, setPageSize] = useState(20)
      const [q, setQ] = useState('')
      const [kind, setKind] = useState('')
      const [dateFrom, setDateFrom] = useState('')
      const [dateTo, setDateTo] = useState('')
      const [data, setData] = useState({ assets: [], total: 0, has_more: false })
      const [loading, setLoading] = useState(false)
      const [busy, setBusy] = useState(false)
      const [err, setErr] = useState('')
      const [notice, setNotice] = useState('')
      const totalPages = Math.max(1, Math.ceil((data.total || 0) / pageSize))
      useEffect(() => { if (page > totalPages) setPage(totalPages) }, [page, totalPages])
      const load = useCallback(async () => {
        setLoading(true); setErr('')
        try {
          const params = new URLSearchParams({ offset: String((page - 1) * pageSize), limit: String(pageSize), q, kind, from: dateFrom, to: dateTo })
          const d = await api('/assets?' + params.toString())
          setData({ assets: d.assets || [], total: d.total || 0, has_more: Boolean(d.has_more) })
        } catch (e) { setErr(String(e.message || e)) } finally { setLoading(false) }
      }, [page, pageSize, q, kind, dateFrom, dateTo])
      useEffect(() => { void load() }, [load])
      useEffect(() => { const t = setTimeout(() => setPage(1), 250); return () => clearTimeout(t) }, [q, kind])
      const upload = async (event) => {
        const all = Array.from(event.currentTarget.files || [])
        event.currentTarget.value = ''
        const picked = all.filter((file) => file.type.startsWith('image/') || file.type.startsWith('video/'))
        if (!picked.length) {
          setErr('仅支持图片和视频素材')
          return
        }
        setBusy(true); setErr(''); setNotice(picked.length < all.length ? '已忽略非图片/视频文件' : '')
        try {
          let dup = 0
          for (const file of picked) {
            const asset = await uploadFile(file, file.type.startsWith('video') ? 'video' : 'image')
            if (asset.deduplicated) dup += 1
          }
          await onRefresh()
          await load()
          if (dup) setNotice('已存在相同 SHA-256 素材，未新增重复记录')
        } catch (e) { setErr(String(e.message || e)) } finally { setBusy(false) }
      }
      const reveal = async (path) => {
        setErr('')
        try { await api('/reveal', { method: 'POST', body: { path } }) } catch (e) { setErr('打开文件夹失败：' + String(e.message || e)) }
      }
      return h('div', { className: 'adp-page' },
        h('div', { className: 'adp-page-head' },
          h('div', null, h('div', { className: 'adp-eyebrow' }, 'ASSETS'), h('h1', { className: 'adp-title' }, '素材库')),
          h('div', { className: 'adp-row' },
            h('button', { className: 'adp-btn', onClick: () => reveal('assets') }, '打开素材文件夹'),
            h('label', { className: 'adp-btn primary adp-upload-label', title: '仅支持图片和视频' },
              busy ? '上传中…' : '上传素材',
              h('input', { type: 'file', accept: 'image/*,video/*', multiple: true, onChange: upload, disabled: busy, style: { position: 'absolute', width: 1, height: 1, opacity: 0, clip: 'rect(0 0 0 0)', overflow: 'hidden' } })
            )
          )
        ),
        h('div', { className: 'adp-toolbar' },
          h('input', { className: 'adp-input adp-grow', value: q, placeholder: '按名称搜索素材', onChange: (e) => { setQ(e.currentTarget.value); setPage(1) } }),
          h('select', { className: 'adp-select', value: kind, onChange: (e) => { setKind(e.currentTarget.value); setPage(1) } }, h('option', { value: '' }, '全部类型'), h('option', { value: 'image' }, '图片'), h('option', { value: 'video' }, '视频')),
          h('input', { className: 'adp-input adp-date-input', type: 'date', title: '开始日期', value: dateFrom, onChange: (e) => { setDateFrom(e.currentTarget.value); setPage(1) } }),
          h('span', { className: 'adp-small adp-muted' }, '至'),
          h('input', { className: 'adp-input adp-date-input', type: 'date', title: '结束日期', value: dateTo, onChange: (e) => { setDateTo(e.currentTarget.value); setPage(1) } }),
          h('select', { className: 'adp-select', value: pageSize, title: '每页数量', onChange: (e) => { setPageSize(Number(e.currentTarget.value)); setPage(1) } }, [20, 40, 80, 100, 200].map((n) => h('option', { key: n, value: n }, '每页 ' + n))),
          h('button', { className: 'adp-btn', onClick: load, disabled: loading }, loading ? '加载中…' : '刷新')
        ),
        notice ? h('div', { className: 'adp-notice' }, notice) : null,
        err ? h('div', { className: 'adp-error' }, err) : null,
        h('div', { className: 'adp-asset-grid' }, (data.assets || []).map((a) => h('div', { key: a.id, className: 'adp-asset-card' },
          a.kind === 'image' ? h('img', { src: mediaUrl(a.path), alt: a.name }) : h('video', { src: mediaUrl(a.path), muted: true, playsInline: true }),
          h('div', { className: 'adp-asset-card-body' },
            h('div', { className: 'adp-small adp-grow', title: a.name }, a.name),
            h('button', { className: 'adp-icon-btn', title: '在文件夹中显示', onClick: () => reveal(a.path) }, h(Glyph, { name: 'folder', size: 19 }))
          ),
          h('div', { className: 'adp-asset-meta-row' },
            h('span', { className: 'adp-asset-kind' }, assetMeta(a)),
            h('span', { className: 'adp-asset-time', title: fmtAssetDate(a.created_at) }, fmtAssetDate(a.created_at))
          )
        ))),
        !loading && !(data.assets || []).length ? h('div', { className: 'adp-empty-state' }, '没有匹配的素材') : null,
        h('div', { className: 'adp-pager' },
          h('button', { className: 'adp-btn', disabled: page <= 1 || loading, onClick: () => setPage((v) => Math.max(1, v - 1)) }, '上一页'),
          h('span', { className: 'adp-small adp-muted' }, '第 ' + page + ' / ' + totalPages + ' 页 · ' + (data.total || 0) + ' 个'),
          h('button', { className: 'adp-btn', disabled: page >= totalPages || loading, onClick: () => setPage((v) => v + 1) }, '下一页')
        )
      )
    }

    function TasksTab({ onOpen }) {
      const [page, setPage] = useState(1)
      const [pageSize, setPageSize] = useState(20)
      const [q, setQ] = useState('')
      const [dateFrom, setDateFrom] = useState('')
      const [dateTo, setDateTo] = useState('')
      const [status, setStatus] = useState('')
      const [data, setData] = useState({ runs: [], total: 0, has_more: false })
      const [loading, setLoading] = useState(false)
      const [err, setErr] = useState('')
      const [notice, setNotice] = useState('')
      const [selectedIds, setSelectedIds] = useState([])
      const [busy, setBusy] = useState('')
      const totalPages = Math.max(1, Math.ceil((data.total || 0) / pageSize))
      useEffect(() => { if (page > totalPages) setPage(totalPages) }, [page, totalPages])
      const load = useCallback(async () => {
        setLoading(true); setErr('')
        try {
          const params = new URLSearchParams({ offset: String((page - 1) * pageSize), limit: String(pageSize), q, status, from: dateFrom, to: dateTo, sort: 'created_desc' })
          const d = await api('/runs?' + params.toString())
          setData({ runs: d.runs || [], total: d.total || 0, has_more: Boolean(d.has_more) })
        } catch (e) { setErr(String(e.message || e)) } finally { setLoading(false) }
      }, [page, pageSize, q, status, dateFrom, dateTo])
      useEffect(() => { void load() }, [load])
      useEffect(() => { const t = setTimeout(() => setPage(1), 250); return () => clearTimeout(t) }, [q])
      const select = (id) => setSelectedIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : prev.concat(id))
      const pageSelectable = (data.runs || []).filter((r) => r.status === 'succeeded').map((r) => r.id)
      const pageAllSelected = pageSelectable.length > 0 && pageSelectable.every((id) => selectedIds.includes(id))
      const togglePage = () => {
        if (pageAllSelected) setSelectedIds((prev) => prev.filter((id) => !pageSelectable.includes(id)))
        else setSelectedIds((prev) => Array.from(new Set(prev.concat(pageSelectable))))
      }
      const clearAll = () => setSelectedIds([])
      const exportSelected = async () => {
        if (!selectedIds.length) { setErr('先选择已完成任务'); return }
        setBusy('export'); setErr(''); setNotice('')
        try { await downloadPost('/runs/export', { run_ids: selectedIds }, 'adplus-export.zip'); setNotice('已导出 ' + selectedIds.length + ' 个任务') } catch (e) { setErr(String(e.message || e)) } finally { setBusy('') }
      }
      const renamed = (id, title) => setData((prev) => Object.assign({}, prev, { runs: (prev.runs || []).map((r) => r.id === id ? Object.assign({}, r, { title }) : r) }))
      return h('div', { className: 'adp-page' },
        h('div', { className: 'adp-page-head' },
          h('div', null, h('div', { className: 'adp-eyebrow' }, 'TASKS'), h('h1', { className: 'adp-title' }, '任务')),
          h('div', { className: 'adp-row' },
            h('button', { className: 'adp-btn', onClick: load, disabled: loading }, loading ? '加载中…' : '刷新'),
            h('button', { className: 'adp-btn', onClick: togglePage, disabled: loading }, pageAllSelected ? '取消当前页' : '全选当前页'),
            selectedIds.length ? h('button', { className: 'adp-btn ghost', onClick: clearAll, disabled: !!busy }, '取消全部选择 (' + selectedIds.length + ')') : null,
            h('button', { className: 'adp-btn primary', onClick: exportSelected, disabled: !selectedIds.length || !!busy }, busy === 'export' ? '导出中…' : '导出选中 (' + selectedIds.length + ')')
          )
        ),
        h('div', { className: 'adp-toolbar' },
          h('input', { className: 'adp-input adp-grow', value: q, placeholder: '搜索任务名称 / ID', onChange: (e) => { setQ(e.currentTarget.value); setPage(1) } }),
          h('input', { className: 'adp-input', type: 'date', value: dateFrom, title: '开始日期', onChange: (e) => { setDateFrom(e.currentTarget.value); setPage(1) } }),
          h('span', { className: 'adp-small adp-muted' }, '至'),
          h('input', { className: 'adp-input', type: 'date', value: dateTo, title: '结束日期', onChange: (e) => { setDateTo(e.currentTarget.value); setPage(1) } }),
          h('select', { className: 'adp-select', value: status, onChange: (e) => { setStatus(e.currentTarget.value); setPage(1) } },
            h('option', { value: '' }, '全部状态'), h('option', { value: 'succeeded' }, '完成'), h('option', { value: 'running' }, '生成中'), h('option', { value: 'failed' }, '失败'), h('option', { value: 'canceled' }, '已取消')
          ),
          h('select', { className: 'adp-select', value: pageSize, title: '每页数量', onChange: (e) => { setPageSize(Number(e.currentTarget.value)); setPage(1) } },
            [20, 40, 80, 100, 200].map((n) => h('option', { key: n, value: n }, '每页 ' + n))
          )
        ),
        notice ? h('div', { className: 'adp-notice' }, notice) : null,
        err ? h('div', { className: 'adp-error' }, err) : null,
        h('div', { className: 'adp-task-grid' }, (data.runs || []).map((r) => h(TaskCard, { key: r.id, run: r, onOpen, selected: selectedIds.includes(r.id), onSelect: select, onRenamed: renamed }))),
        !loading && !(data.runs || []).length ? h('div', { className: 'adp-empty-state' }, '没有匹配的任务') : null,
        h('div', { className: 'adp-pager' },
          h('button', { className: 'adp-btn', disabled: page <= 1 || loading, onClick: () => setPage((v) => Math.max(1, v - 1)) }, '上一页'),
          h('span', { className: 'adp-small adp-muted' }, '第 ' + page + ' / ' + totalPages + ' 页 · ' + (data.total || 0) + ' 个任务'),
          h('button', { className: 'adp-btn', disabled: page >= totalPages || loading, onClick: () => setPage((v) => v + 1) }, '下一页')
        )
      )
    }

    function PersonasTab({ personas, onRefresh }) {
      const empty = () => ({ name: '', type: 'ai', gender: 'any', age: 'youth', body_type: 'standard', ethnicity: 'asian', exact_age: '', height_cm: '', hair: '', outfit: '', temperament: '', voice_tone: '', role: 'both', consent: { confirmed: false, note: '' } })
      const [open, setOpen] = useState(false)
      const [form, setForm] = useState(empty)
      const [editingId, setEditingId] = useState('')
      const [busy, setBusy] = useState('')
      const [err, setErr] = useState('')
      const set = (key, value) => setForm((prev) => Object.assign({}, prev, { [key]: value }))
      const openNew = () => { setEditingId(''); setForm(empty()); setErr(''); setOpen(true) }
      const openEdit = (persona) => { setEditingId(persona.id); setForm(Object.assign(empty(), persona)); setErr(''); setOpen(true) }
      const close = () => { if (busy === 'save') return; setOpen(false); setEditingId(''); setErr('') }
      const save = async () => {
        setBusy('save'); setErr('')
        try {
          const payload = Object.assign({}, form)
          payload.name = String(payload.name || '').trim() || '未命名模特'
          if (payload.exact_age === '' || payload.exact_age == null) delete payload.exact_age
          if (payload.height_cm === '' || payload.height_cm == null) delete payload.height_cm
          if (payload.type === 'real' && !(payload.consent && payload.consent.confirmed)) throw new Error('真人模特必须勾选授权')
          await api(editingId ? '/personas/' + editingId : '/personas', { method: editingId ? 'PATCH' : 'POST', body: payload })
          await onRefresh(); close()
        } catch (e) { setErr(String(e.message || e)) } finally { setBusy('') }
      }
      const remove = async (persona) => {
        if (!window.confirm('删除模特「' + persona.name + '」？')) return
        setBusy('remove:' + persona.id); setErr('')
        try { await api('/personas/' + persona.id, { method: 'DELETE' }); await onRefresh(); if (editingId === persona.id) close() } catch (e) { setErr(String(e.message || e)) } finally { setBusy('') }
      }
      const summary = (p) => [p.gender, p.age, p.body_type, p.ethnicity].filter(Boolean).join(' · ')
      return h('div', { className: 'adp-page' },
        h('div', { className: 'adp-page-head' },
          h('div', null, h('div', { className: 'adp-eyebrow' }, 'CAST LIBRARY'), h('h1', { className: 'adp-title' }, '模特库')),
          h('button', { className: 'adp-btn primary', onClick: openNew }, '新建模特')
        ),
        h('div', { className: 'adp-persona-grid' },
          (personas || []).map((p) => h('div', { key: p.id, className: 'adp-persona-card' },
            h('div', { className: 'adp-row' }, h('div', { className: 'adp-h2 adp-grow' }, p.name || '未命名'), h(Badge, { status: p.type === 'real' ? (p.consent && p.consent.confirmed ? 'ok' : 'bad') : '' }, p.type === 'real' ? '真人' : p.type === 'group' ? '群像' : 'AI')),
            h('div', { className: 'adp-small adp-muted', style: { marginTop: 4 } }, summary(p) || '未设置'),
            h('div', { className: 'adp-small adp-faint', style: { marginTop: 3 } }, '角色：' + ({ both: '出镜+口播', A: '口播 A', B: '口播 B', group: '群像' }[p.role] || p.role || '—') + (p.used_in_runs && p.used_in_runs.length ? ' · 已用 ' + p.used_in_runs.length + ' 次' : '')),
            h('div', { className: 'adp-row', style: { marginTop: 10 } },
              h('button', { className: 'adp-btn', onClick: () => openEdit(p) }, '编辑'),
              h('button', { className: 'adp-btn danger', onClick: () => remove(p), disabled: busy === 'remove:' + p.id }, '删除')
            )
          )),
          !(personas || []).length ? h('div', { className: 'adp-empty-state' }, h('div', { className: 'adp-h2' }, '还没有模特'), h('div', { className: 'adp-small adp-muted' }, '新建一个角色，之后在爆款复刻里直接复用。'), h('button', { className: 'adp-btn primary', onClick: openNew }, '新建模特')) : null
        ),
        err && !open ? h('div', { className: 'adp-error', style: { marginTop: 12 } }, err) : null,
        open ? h('div', { className: 'adp-modal-backdrop', onClick: close },
          h('div', { className: 'adp-modal adp-persona-modal', role: 'dialog', 'aria-modal': 'true', 'aria-label': '编辑模特', onClick: (e) => e.stopPropagation() },
            h('div', { className: 'adp-modal-head' },
              h('div', null, h('div', { className: 'adp-h2' }, editingId ? '编辑模特' : '新建模特'), h('div', { className: 'adp-small adp-muted' }, '固定人物设定，复用到不同片子。')),
              h('button', { className: 'adp-icon-btn', onClick: close, title: '关闭' }, h(Glyph, { name: 'close' }))
            ),
            h('div', { className: 'adp-modal-body' },
              h('div', { className: 'adp-modal-section' },
                h('div', { className: 'adp-modal-section-title' }, '基础信息'),
                h('div', { className: 'adp-field-grid g2' },
                  h(Field, { label: '名称', style: { gridColumn: '1 / -1' } }, h('input', { className: 'adp-input', value: form.name || '', placeholder: '例如：小美·追剧场景', onChange: (e) => set('name', e.currentTarget.value) })),
                  h(FormSelect, { label: '类型', value: form.type || 'ai', onChange: (x) => set('type', x), options: [{ value: 'ai', label: 'AI 模特' }, { value: 'real', label: '真人（需授权）' }, { value: 'group', label: '群像' }] }),
                  h(FormSelect, { label: '角色', value: form.role || 'both', onChange: (x) => set('role', x), options: [{ value: 'both', label: '出镜+口播' }, { value: 'A', label: '口播 A' }, { value: 'B', label: '口播 B' }, { value: 'group', label: '群像' }] })
                )
              ),
              h('div', { className: 'adp-modal-section' },
                h('div', { className: 'adp-modal-section-title' }, '人物特征'),
                h(PersonaFields, { value: form, onChange: (v) => setForm(Object.assign({}, form, v)), columns: 2 })
              ),
              h('div', { className: 'adp-modal-section' },
                h('div', { className: 'adp-modal-section-title' }, '细节'),
                h('div', { className: 'adp-field-grid g2' },
                  h(Field, { label: '具体年龄', hint: '可选，精确控制人物年龄' }, h('input', { className: 'adp-input', type: 'number', value: form.exact_age || '', onChange: (e) => set('exact_age', e.currentTarget.value ? Number(e.currentTarget.value) : '') })),
                  h(Field, { label: '身高 cm', hint: '可选，用于保持人物比例' }, h('input', { className: 'adp-input', type: 'number', value: form.height_cm || '', onChange: (e) => set('height_cm', e.currentTarget.value ? Number(e.currentTarget.value) : '') }))
                )
              ),
              h('div', { className: 'adp-modal-section' },
                h('div', { className: 'adp-modal-section-title' }, '风格与声线'),
                h('div', { className: 'adp-field-grid g2' },
                  h(Field, { label: '发型' }, h('input', { className: 'adp-input', value: form.hair || '', placeholder: '例如：低马尾', onChange: (e) => set('hair', e.currentTarget.value) })),
                  h(Field, { label: '服装' }, h('input', { className: 'adp-input', value: form.outfit || '', placeholder: '例如：米色针织衫', onChange: (e) => set('outfit', e.currentTarget.value) })),
                  h(Field, { label: '气质' }, h('input', { className: 'adp-input', value: form.temperament || '', placeholder: '例如：松弛、生活化', onChange: (e) => set('temperament', e.currentTarget.value) })),
                  h(Field, { label: '声线' }, h('input', { className: 'adp-input', value: form.voice_tone || '', placeholder: '例如：偏低、语速快', onChange: (e) => set('voice_tone', e.currentTarget.value) }))
                )
              ),
              form.type === 'real' ? h('label', { className: 'adp-check' }, h('input', { type: 'checkbox', checked: Boolean(form.consent && form.consent.confirmed), onChange: (e) => set('consent', { confirmed: e.currentTarget.checked, note: '模特库手动确认' }) }), '我确认已取得该真人的肖像/声音使用授权') : null,
              err ? h('div', { className: 'adp-error' }, err) : null
            ),
            h('div', { className: 'adp-modal-foot' },
              h('button', { className: 'adp-btn ghost', onClick: close }, '取消'),
              h('button', { className: 'adp-btn primary', onClick: save, disabled: busy === 'save' }, busy === 'save' ? '保存中…' : (editingId ? '保存修改' : '创建模特'))
            )
          )
        ) : null
      )
    }


    const REMAKE_TIER_LABELS = { full: '完整复刻', reference: '参考生成', generation: '仅生成', image_only: '图片', none: '不可用' }

    /** Read-only capability contract; the editable defaults sit below it. */
    function CapabilityDetail({ model, onSaved }) {
      const io = model.io || {}
      const remake = model.remake || {}
      const videos = io.videos
      const images = io.images
      const audio = io.audio
      const bits = []
      if (videos) bits.push('视频 ≤' + videos.max + ' 段 · ' + videos.min_s + '–' + videos.max_s + 's · 合计 ≤' + videos.total_s + 's · ≤' + videos.max_mb + 'MB')
      if (images) bits.push('图片 ≤' + images.max + ' 张 · ≤' + images.max_mb + 'MB')
      if (audio) bits.push('音频 ≤' + audio.max + ' 段 · ≤' + audio.max_s + 's')
      const outputs = []
      if ((model.output || {}).video) outputs.push('视频')
      if ((model.output || {}).audio) outputs.push('音频')
      if ((model.output || {}).image) outputs.push('图片')
      return h('details', { className: 'adp-model-cap' },
        h('summary', null, '能力与参数'),
        h('div', { className: 'adp-col', style: { gap: 6, marginTop: 6 } },
          h('div', { className: 'adp-small' }, '复刻等级：' + (REMAKE_TIER_LABELS[remake.tier] || remake.tier || '—') + (remake.real_person_reference === 'restricted' ? ' · 真人参考受限' : remake.real_person_reference === 'allowed' ? ' · 支持真人参考' : '')),
          bits.length ? h('div', { className: 'adp-small adp-muted' }, bits.join('；')) : null,
          h('div', { className: 'adp-small adp-muted' }, '输出：' + (outputs.join(' + ') || '—') + ((model.params || {}).resolution && (model.params || {}).resolution.enum ? ' · 分辨率 ' + model.params.resolution.enum.join('/') : '')),
          h(ModelParamEditor, { model, onSaved })
        )
      )
    }

    /** Editable per-model defaults. Values are validated again by the engine. */
    function ModelParamEditor({ model, onSaved }) {
      const [values, setValues] = useState(() => Object.assign({}, model.default_params || {}))
      const [busy, setBusy] = useState(false)
      const [note, setNote] = useState('')
      useEffect(() => { setValues(Object.assign({}, model.default_params || {})); setNote('') }, [model.id, JSON.stringify(model.default_params || {})])
      const params = model.params || {}
      const set = (key, value) => setValues((prev) => Object.assign({}, prev, { [key]: value }))
      const save = async () => {
        setBusy(true); setNote('')
        try {
          const data = await api('/settings/model_params', { method: 'POST', body: { model_id: model.id, values } })
          setNote(data.ok ? '已保存' : '未保存')
          if (data.ok && onSaved) await onSaved()
        } catch (e) { setNote(String(e.message || e)) } finally { setBusy(false) }
      }
      const fields = []
      if (params.resolution && params.resolution.enum) {
        fields.push(h(FormSelect, { key: 'resolution', label: '默认清晰度', value: String(values.resolution || params.resolution.default || ''), onChange: (x) => set('resolution', x), options: params.resolution.enum.map((x) => ({ value: x, label: x })) }))
      }
      if (params.aspect && params.aspect.enum) {
        fields.push(h(FormSelect, { key: 'aspect', label: '默认比例', value: String(values.aspect || params.aspect.default || ''), onChange: (x) => set('aspect', x), options: params.aspect.enum.map((x) => ({ value: x, label: x })) }))
      }
      if (params.area && params.area.enum) {
        fields.push(h(FormSelect, { key: 'area', label: '默认尺寸', value: String(values.area || params.area.default || ''), onChange: (x) => set('area', x), options: params.area.enum.map((x) => ({ value: x, label: x })) }))
      }
      if (params.duration) {
        const options = []
        if (params.duration.follow_reference) options.push({ value: 'reference', label: '跟随参考片' })
        const durations = model.id === 'minimax.h3' ? [] : (model.durations || [])
        if (durations.length) durations.forEach((x) => options.push({ value: String(x), label: x + 's' }))
        else if (params.duration.min != null && params.duration.max != null) options.push({ value: String(params.duration.default || params.duration.min), label: params.duration.min + '–' + params.duration.max + 's' })
        fields.push(h(FormSelect, { key: 'duration', label: '默认时长', value: String(model.id === 'minimax.h3' ? 'reference' : (values.duration || 'reference')), onChange: (x) => set('duration', x === 'reference' ? 'reference' : Number(x)), options }))
      }
      if (params.generate_audio) {
        fields.push(h('label', { key: 'audio', className: 'adp-check' }, h('input', { type: 'checkbox', checked: values.generate_audio !== false, onChange: (e) => set('generate_audio', e.currentTarget.checked) }), '生成原生音频'))
      }
      if (!fields.length) return null
      return h('div', { className: 'adp-col', style: { gap: 6, marginTop: 4 } },
        h('div', { className: 'adp-field-grid g3' }, fields),
        h('div', { className: 'adp-row', style: { gap: 8 } },
          h('button', { className: 'adp-btn ghost', onClick: save, disabled: busy }, busy ? '保存中…' : '保存默认参数'),
          note ? h('span', { className: 'adp-small adp-muted' }, note) : null
        )
      )
    }

    const TEXT_STATUS_LABEL = { ok: '已开通', not_open: '未开通', no_key: '未配置 key', unknown: '未检测', error: '调用异常', rate: '限流' }

    /** The fallback ladder DSH schedules from, rendered read-only. */
    function VisionChainCard({ scheduling }) {
      const chain = (scheduling && scheduling.vision) || []
      if (!chain.length) return null
      return h('div', { className: 'adp-card adp-col', style: { margin: '4px 0 8px' } },
        h('div', { className: 'adp-row' },
          h('div', { className: 'adp-h2 adp-grow' }, '参考片拆解视觉链'),
          h('span', { className: 'adp-small adp-muted' }, '按顺序自动降级，首个成功即停止')
        ),
        h('div', { className: 'adp-chain' }, chain.map((stage, index) => h('div', { key: stage.id, className: 'adp-chain-step' },
          h('div', { className: 'adp-chain-node' + (stage.available ? ' on' : ' off'), title: stage.reason || '' },
            h('span', { className: 'adp-chain-dot' }),
            h('span', { className: 'adp-chain-name' }, stage.label),
            h('span', { className: 'adp-chain-state' }, stage.available ? '可用' : (stage.reason || '不可用'))
          ),
          index < chain.length - 1 ? h('span', { className: 'adp-chain-arrow' }, '→') : null
        ))),
        h('div', { className: 'adp-small adp-muted', style: { marginTop: 6 } }, 'DSH 可通过 adclip_get_analysis 读到实际使用的 provider/model。')
      )
    }

    function RemakeChainCard({ scheduling }) {
      const chain = (scheduling && scheduling.remake) || []
      if (!chain.length) return null
      return h('div', { className: 'adp-card adp-col', style: { margin: '4px 0 8px' } },
        h('div', { className: 'adp-row' },
          h('div', { className: 'adp-h2 adp-grow' }, '爆款复刻梯度'),
          h('span', { className: 'adp-small adp-muted' }, '按档降级，首个可用档胜出')
        ),
        h('div', { className: 'adp-chain' }, chain.map((stage, index) => h('div', { key: stage.rung, className: 'adp-chain-step' },
          h('div', { className: 'adp-chain-node' + (stage.available ? ' on' : ' off'), title: stage.reason || '' },
            h('span', { className: 'adp-chain-dot' }),
            h('span', { className: 'adp-chain-name' }, stage.label),
            h('span', { className: 'adp-chain-state' }, stage.available ? (stage.model_label || '可用') : (stage.reason || '不可用'))
          ),
          index < chain.length - 1 ? h('span', { className: 'adp-chain-arrow' }, '→') : null
        ))),
        h('div', { className: 'adp-small adp-muted', style: { marginTop: 6 } }, '每次降级都会记到 selection.history；DSH 可通过 adclip_get_run 读取。')
      )
    }

    /** Doubao-Seed-2.1 rows: capability tags, context, endpoint, activation. */
    function TextModelsCard({ textModels, onRefresh }) {
      const [busy, setBusy] = useState(false)
      const [note, setNote] = useState('')
      const rows = textModels || []
      const probe = async () => {
        setBusy(true); setNote('')
        try {
          const data = await api('/text/models/probe', { method: 'POST', body: {} })
          const results = data.results || []
          const ok = results.filter((row) => row.ok).length
          setNote(ok ? `${ok}/${results.length} 个模型已开通` : '都没有开通：去方舟控制台「开通管理」开通 Doubao-Seed-2.1')
          await onRefresh()
        } catch (e) { setNote(String(e.message || e)) } finally { setBusy(false) }
      }
      return h('div', { className: 'adp-card adp-col', style: { margin: '4px 0 8px' } },
        h('div', { className: 'adp-row' },
          h('div', null,
            h('div', { className: 'adp-h2' }, '文本 / 视觉模型'),
            h('div', { className: 'adp-small adp-muted' }, 'Doubao-Seed-2.1 系列 · 用 ARK_API_KEY 直接调 /chat/completions')
          ),
          h('div', { className: 'adp-grow' }),
          h('button', { className: 'adp-btn ghost', disabled: busy, onClick: probe }, busy ? '检测中…' : '检测开通状态')
        ),
        rows.length ? rows.map((model) => {
          const status = model.status === 'ok' ? 'ok' : (model.available ? 'unknown' : (model.status || 'no_key'))
          const badge = TEXT_STATUS_LABEL[status] || status
          return h('div', { key: model.id, className: 'adp-provider-model adp-textmodel-row' },
            h('div', { className: 'adp-grow' },
              h('div', { className: 'adp-provider-model-name' }, model.label || model.id),
              h('div', { className: 'adp-model-tags' }, (model.tags || []).map((tag) => h('span', { key: tag, className: 'adp-model-tag' }, tag))),
              h('div', { className: 'adp-small adp-muted' }, '上下文 ' + (model.context || '—') + ' · ' + (model.endpoint || '') + ' · model=' + (model.ark_model || '')),
              model.reason ? h('div', { className: 'adp-small adp-faint' }, model.reason) : null
            ),
            h('span', { className: 'adp-badge' + (status === 'ok' ? ' ok' : (status === 'not_open' || status === 'no_key' ? ' warn' : '')) }, badge)
          )
        }) : h('div', { className: 'adp-small adp-muted' }, '正在读取模型列表…'),
        note ? h('div', { className: 'adp-small adp-muted' }, note) : null,
        h('div', { className: 'adp-small adp-faint' }, '打开本页会自动检测一次；刚开通时方舟可能要 1–2 分钟同步，未开通时视觉链自动跳到 DSH 视觉桥、文本生成回落到 DSH 模型。')
      )
    }

    function SettingsTab({ health, models, assets, textModels, scheduling, onRefresh, engine, onSetup }) {
      const [engineBusy, setEngineBusy] = useState(false)
      const [keys, setKeys] = useState([])
      const [values, setValues] = useState({})
      const [openModels, setOpenModels] = useState({})
      const [busy, setBusy] = useState('')
      const [err, setErr] = useState('')
      const [notice, setNotice] = useState('')
      const [refreshing, setRefreshing] = useState(false)
      useEffect(() => {
        api('/settings/keys').then((d) => setKeys(d.keys || [])).catch((e) => setErr(String(e.message || e)))
      }, [])
      // Refresh the Ark activation state in the background on every visit, so a
      // model the user just enabled in the console shows up without a manual check.
      useEffect(() => {
        let alive = true
        ;(async () => {
          try {
            await api('/text/models/probe', { method: 'POST', body: {} })
            if (alive) await onRefresh()
          } catch { /* keep the last known state */ }
        })()
        return () => { alive = false }
      }, [])
      const providers = [
        { id: 'minimax', name: 'MiniMax', key: 'MINIMAX_API_KEY', desc: 'H3 原生对白 / Hailuo 图生视频 / H3 Image' },
        { id: 'ark', name: '火山方舟', key: 'ARK_API_KEY', desc: 'Seedance 2.5 / 2.0 · Seedream 4.0' },
        { id: 'kling', name: 'Kling 可灵', key: 'KLING_API_KEY', desc: 'Kling v3 原生音频' },
      ]
      const statusFor = (name) => (keys || []).find((k) => k.name === name) || { present: false, masked: '' }
      const modelsFor = (provider) => (models || []).filter((m) => m.provider === provider)
      const save = async (name, override) => {
        const value = override === undefined ? (values[name] || '') : override
        setBusy(name); setErr(''); setNotice('')
        try {
          const data = await api('/settings/keys', { method: 'POST', body: { name, value } })
          setKeys(data.keys || [])
          setValues((prev) => Object.assign({}, prev, { [name]: '' }))
          setOpenModels((prev) => Object.assign({}, prev, { [name]: true }))
          await onRefresh()
          setNotice(value ? '已保存，已自动刷新该厂商模型' : '已清除该厂商 key，模型状态已刷新')
        } catch (e) { setErr(String(e.message || e)) } finally { setBusy('') }
      }
      const refresh = async () => {
        setRefreshing(true); setErr(''); setNotice('')
        try { await onRefresh(); setNotice('模型列表已刷新') } catch (e) { setErr(String(e.message || e)) } finally { setRefreshing(false) }
      }
      const enabledModels = (models || []).filter((m) => m.enabled !== false).map((m) => m.id)
      const saveEnabled = async (ids, label) => {
        setBusy('models'); setErr(''); setNotice('')
        try {
          await api('/settings/models', { method: 'POST', body: { enabled: ids } })
          await onRefresh()
          setNotice(label || '模型启用状态已更新')
        } catch (e) { setErr(String(e.message || e)) } finally { setBusy('') }
      }
      const toggleModel = (model) => {
        const checked = model.enabled === false
        const next = checked ? enabledModels.concat(model.id) : enabledModels.filter((id) => id !== model.id)
        saveEnabled(next, (checked ? '已启用 ' : '已停用 ') + model.label)
      }
      const toggleProvider = (providerModels) => {
        const ids = providerModels.map((m) => m.id)
        const all = ids.every((id) => enabledModels.includes(id))
        const next = all ? enabledModels.filter((id) => !ids.includes(id)) : Array.from(new Set(enabledModels.concat(ids)))
        saveEnabled(next, all ? '已停用该厂商模型' : '已启用该厂商模型')
      }
      return h('div', { className: 'adp-page adp-settings-page' },
        h('div', { className: 'adp-page-head' },
          h('div', null,
            h('div', { className: 'adp-eyebrow' }, 'SETTINGS / MODELS'),
            h('h1', { className: 'adp-title' }, '设置与模型')
          ),
          h('div', { className: 'adp-row' }, health ? h(Badge, { status: health.ok ? 'ok' : 'bad' }, health.ok ? '引擎在线' : '引擎离线') : null, h('button', { className: 'adp-btn', onClick: refresh, disabled: refreshing }, refreshing ? '刷新中…' : '刷新模型'), h('button', { className: 'adp-btn ghost', onClick: async () => { try { await api('/reveal', { method: 'POST', body: { path: '' } }) } catch (e) { setErr(String(e.message || e)) } } }, '打开数据文件夹'))
        ),
        health ? h('div', { className: 'adp-small adp-muted', style: { marginBottom: 14 } }, '服务：' + (health.service || '—') + ' · 数据：' + (health.data || '—') + ' · 运行：' + (health.runs ?? '—')) : null,
        h('div', { className: 'adp-card adp-col', style: { margin: '4px 0 8px' } },
          h('div', { className: 'adp-row' },
            h('div', { className: 'adp-h2 adp-grow' }, '引擎运行时'),
            engine
              ? h(Badge, { status: engine.ok ? 'ok' : ((engine.boot && engine.boot.stage === 'preparing') ? 'warn' : 'bad') }, engine.ok ? '在线' : engineStageLabel(engine))
              : h(Badge, null, '未连接')
          ),
          h('div', { className: 'adp-small adp-muted' }, engine ? (engine.detail || '—') : '尚未拿到 Host 状态'),
          engine && engine.ok ? h('div', { className: 'adp-small adp-faint', style: { marginTop: 3 } }, '端口 ' + (engine.port || '—') + ' · 解释器 ' + (engine.python || '—') + (engine.boot && engine.boot.source ? ' · ' + engine.boot.source : '')) : null,
          health && health.deps && health.deps.ok === false ? h('div', { className: 'adp-small adp-error', style: { marginTop: 4 } }, health.deps.hint) : null,
          h('div', { className: 'adp-row', style: { marginTop: 8 } },
            h('button', { className: 'adp-btn', disabled: engineBusy, onClick: async () => { setEngineBusy(true); setErr(''); try { await restartEngineHost(); setNotice('已请求重新启动引擎，状态会自动刷新') } catch (e) { setErr(String(e.message || e)) } finally { setEngineBusy(false) } } }, engineBusy ? '重启中…' : '重新启动引擎'),
            h('button', { className: 'adp-btn ghost', onClick: onSetup }, '环境检查'),
            h('span', { className: 'adp-small adp-muted' }, '首次启动会在数据目录里准备 Python 依赖，约 1 分钟')
          )
        ),
        h('div', { className: 'adp-section-head', style: { marginTop: 20 } }, h('span', { className: 'adp-section-title' }, '视频服务商'), h('span', { className: 'adp-section-note' }, '勾选后才会出现在生成页')),
        h('div', { className: 'adp-provider-grid' }, providers.map((p) => {
          const st = statusFor(p.key)
          const providerModels = modelsFor(p.id)
          const enabledProviderModels = providerModels.filter((m) => m.enabled !== false)
          const openModelsForProvider = Boolean(openModels[p.key])
          return h('section', { key: p.id, className: 'adp-provider-card' + (st.present ? ' configured' : '') },
            h('div', { className: 'adp-provider-head' },
              h('div', null, h('div', { className: 'adp-provider-name' }, p.name), h('div', { className: 'adp-small adp-muted' }, p.desc)),
              h('div', { className: 'adp-row', style: { gap: 6 } },
                st.present ? h(Badge, { status: 'ok' }, '已配置') : h(Badge, null, '未配置'),
                providerModels.length ? h('button', { className: 'adp-btn ghost', disabled: busy === 'models', onClick: () => toggleProvider(providerModels), title: '切换该厂商全部模型' }, providerModels.every((m) => m.enabled !== false) ? '全不选' : '全选') : null
              )
            ),
            h('div', { className: 'adp-keyrow' },
              h('input', { className: 'adp-input adp-grow', type: 'password', value: values[p.key] || '', placeholder: st.present ? '输入新 key 可替换；留空保存会清除' : '粘贴 ' + p.key, onChange: (e) => { const value = e.currentTarget.value; setValues((prev) => Object.assign({}, prev, { [p.key]: value })) } }),
              h('button', { className: 'adp-btn primary', onClick: () => save(p.key), disabled: busy === p.key }, busy === p.key ? '保存中…' : '保存'),
              st.present ? h('button', { className: 'adp-btn ghost', onClick: () => save(p.key, ''), disabled: busy === p.key, title: '移除该厂商 key' }, '清除') : null
            ),
            st.present ? h('div', { className: 'adp-small adp-muted' }, '已配置：' + st.masked) : h('div', { className: 'adp-small adp-muted' }, '填入 key 后自动加载该厂商模型'),
            h('button', { className: 'adp-models-toggle', onClick: () => setOpenModels((prev) => Object.assign({}, prev, { [p.key]: !openModelsForProvider })) },
              h('span', { className: 'adp-models-toggle-title' }, '模型 ' + providerModels.length),
              h('span', { className: 'adp-small adp-muted' }, '已启用 ' + enabledProviderModels.length + ' / ' + providerModels.length),
              h('span', { className: 'adp-models-toggle-action' }, openModelsForProvider ? '收起' : '展开')
            ),
            !openModelsForProvider && enabledProviderModels.length ? h('div', { className: 'adp-model-summary' }, enabledProviderModels.map((m) => h('span', { key: m.id, className: 'adp-model-summary-chip' }, m.label))) : null,
            openModelsForProvider ? h('div', { className: 'adp-provider-models' },
              providerModels.length ? providerModels.map((m) => h('div', { key: m.id, className: 'adp-provider-model' + (m.available ? ' on' : '') + (m.enabled === false ? ' off' : '') },
                h('div', null, h('div', { className: 'adp-provider-model-name' }, m.label), h(CapabilityChips, { row: m }), h(CapabilityDetail, { model: m, onSaved: onRefresh })),
                h('div', { className: 'adp-row', style: { gap: 5 } }, m.available ? h(Badge, { status: 'ok' }, '可用') : h(Badge, { title: m.reason || '' }, '待 key'), m.native_audio ? h('span', { className: 'adp-small adp-muted' }, '原生对白') : null, h('label', { className: 'adp-model-enable' }, h('input', { type: 'checkbox', checked: m.enabled !== false, disabled: busy === 'models', onChange: () => toggleModel(m), title: '是否出现在生成页' }), '启用'))
              )) : h('div', { className: 'adp-small adp-muted' }, '该厂商暂无可展示模型；保存 key 后刷新。')
            ) : null
          )
        })),
        h('div', { className: 'adp-section-head', style: { marginTop: 20 } }, h('span', { className: 'adp-section-title' }, '文本 / 视觉调度'), h('span', { className: 'adp-section-note' }, '模型来源与降级顺序')),
        h(VisionChainCard, { scheduling }),
        h(RemakeChainCard, { scheduling }),
        h(TextModelsCard, { textModels, onRefresh }),
        notice ? h('div', { className: 'adp-notice' }, notice) : null,
        err ? h('div', { className: 'adp-error', style: { marginTop: 10 } }, err) : null,
        h('div', { className: 'adp-hint', style: { marginTop: 12 } }, '密钥只保存在本机数据目录的 settings.json（权限 0600）；不会回显完整值。生产版应迁移到系统 Keychain。')
      )
    }

    function SetupPage({ preflight, engine, busy, onRecheck, onStart, onSkip }) {
      const [copied, setCopied] = useState('')
      const items = (preflight && preflight.items) || []
      const required = items.filter((i) => i.level === 'required')
      const optional = items.filter((i) => i.level === 'optional')
      const blocking = required.filter((i) => i.status === 'missing')
      const okAll = Boolean(preflight && items.length && blocking.length === 0)
      const copy = async (id, text) => {
        try {
          await navigator.clipboard.writeText(text)
          setCopied(id)
          setTimeout(() => setCopied(''), 1600)
        } catch { /* clipboard denied: the command stays selectable */ }
      }
      const row = (item) => {
        const cls = item.status === 'ok' ? 'ok' : (item.status === 'warn' ? 'warn' : 'bad')
        const remedy = item.remedy
        return h('div', { key: item.id, className: 'adp-setup-item ' + cls },
          h('div', { className: 'adp-setup-ico' }, item.status === 'ok' ? '✓' : (item.status === 'warn' ? '!' : '✕')),
          h('div', null,
            h('div', { className: 'adp-setup-title' }, item.title),
            h('div', { className: 'adp-setup-detail' }, item.detail)
          ),
          remedy && remedy.kind === 'command'
            ? h('button', { className: 'adp-btn ghost', onClick: () => copy(item.id, remedy.command) }, copied === item.id ? '已复制' : '复制命令')
            : null,
          remedy ? h('div', { className: 'adp-setup-fix' },
            remedy.kind === 'command' ? h('div', { className: 'adp-setup-cmd' }, h('code', null, remedy.command)) : null,
            remedy.note ? h('div', { className: 'adp-setup-note' }, remedy.note) : null,
            remedy.url ? h('a', { className: 'adp-small', href: remedy.url, target: '_blank', rel: 'noreferrer' }, '打开下载页 ↗') : null
          ) : null
        )
      }
      const engineLine = !engine
        ? '正在连接 Host…'
        : engine.ok
          ? '引擎已在线（端口 ' + (engine.port || '—') + '）'
          : '引擎' + engineStageLabel(engine) + '：' + ((engine.boot && engine.boot.detail) || engine.detail || '—')
      return h('div', { className: 'adp-setup' },
        h('div', { className: 'adp-setup-hero' },
          h('div', { className: 'adp-eyebrow' }, 'FIRST RUN / SETUP'),
          h('h1', { className: 'adp-title' }, okAll ? '运行环境已就绪' : '首次使用，先准备运行环境'),
          h('p', { className: 'adp-lede' }, okAll
            ? 'AdClip 的引擎和媒体工具都能用了。这套检查 macOS 与 Windows 共用，换机器时还会再跑一次。'
            : 'AdClip 的引擎跑在本机 Python 上，媒体处理依赖 ffmpeg。下面标红的项需要先装好；命令可以直接复制到终端执行，装完回到这里点「重新检测」。')
        ),
        items.length ? h('div', null,
          h('div', { className: 'adp-setup-group' }, '必需'),
          required.map(row),
          optional.length ? h('div', { className: 'adp-setup-group' }, '可选') : null,
          optional.map(row)
        ) : h('div', { className: 'adp-notice' }, '正在检查环境…'),
        h('div', { className: 'adp-small adp-muted', style: { marginTop: 10 } }, engineLine),
        h('div', { className: 'adp-setup-foot' },
          h('button', { className: 'adp-btn', disabled: busy === 'recheck', onClick: onRecheck }, busy === 'recheck' ? '检测中…' : '重新检测'),
          h('div', { className: 'adp-grow' }),
          h('button', { className: 'adp-btn ghost', disabled: busy === 'skip', onClick: onSkip }, '稍后再说'),
          h('button', { className: 'adp-btn primary', disabled: !okAll || busy === 'start', onClick: onStart }, busy === 'start' ? '保存中…' : '开始使用')
        ),
        h('div', { className: 'adp-setup-note', style: { marginTop: 14 } },
          '装完 Python 或 ffmpeg 后先点「重新检测」。如果仍显示缺失，请完全退出 DSH 再打开——已经运行的进程看不到新的 PATH，只重启插件引擎不够。')
      )
    }

    class AdClipBoundary extends React.Component {
      constructor(props) {
        super(props)
        this.state = { error: null }
      }
      static getDerivedStateFromError(error) {
        return { error: error }
      }
      componentDidCatch(error, info) {
        try { console.error('AdClip UI crashed', error, info) } catch { /* noop */ }
      }
      render() {
        if (this.state.error) {
          return h('div', { className: 'adp-root' + (IS_MAC ? ' adp-mac' : '') },
            h('style', null, CSS),
            h('div', { className: 'adp-crash' },
              h('div', { className: 'box' },
                h('h3', null, 'AdClip UI 加载失败'),
                h('div', null, String(this.state.error && (this.state.error.stack || this.state.error.message || this.state.error))),
                h('div', { style: { marginTop: 12 } }, h('button', { className: 'adp-btn', onClick: () => location.reload() }, '重新加载'))
              )
            )
          )
        }
        return this.props.children
      }
    }

    function App() {
      const [tab, setTab] = useState('recreate')
      const [health, setHealth] = useState(null)
      const [models, setModels] = useState([])
      const [dsh, setDsh] = useState(null)
      const rootRef = useRef(null)
      const [sidebarOpen, setSidebarOpen] = useState(false)
      const [runs, setRuns] = useState([])
      const [assets, setAssets] = useState([])
      const [personas, setPersonas] = useState([])
      const [selected, setSelected] = useState(null)
      const [err, setErr] = useState('')
      const [engine, setEngine] = useState(null)
      const [textModels, setTextModels] = useState([])
      const [scheduling, setScheduling] = useState(null)
      const [forceSetup, setForceSetup] = useState(false)
      const [setupBusy, setSetupBusy] = useState('')

      const refresh = useCallback(async () => {
        const state = await hostStatus()
        if (state) setEngine(state)
        if (state && !state.ok) return
        try {
          const [h, m, r, a, p, d, t, c] = await Promise.all([
            api('/health'), api('/models'), api('/runs?limit=20'), api('/assets?limit=60'), api('/personas'),
            api('/dsh/models').catch(() => ({ dsh: null })),
            api('/text/models').catch(() => ({ models: [] })),
            api('/capabilities').catch(() => ({ scheduling: null })),
          ])
          setHealth(h); setModels(m.models || []); setRuns(r.runs || []); setAssets(a.assets || []); setPersonas(p.personas || []); setDsh(d.dsh || null)
          setTextModels(t.models || []); setScheduling(c.scheduling || null)
          setSelected(prev => prev ? (r.runs || []).find(x => x.id === prev.id) || prev : null)
        } catch (e) { if (!isTransientNetworkError(e)) setErr('加载失败：' + String(e.message || e)) }
      }, [])

      useEffect(() => { void refresh() }, [refresh])

      useEffect(() => {
        if (!IS_MAC) return
        const el = rootRef.current
        if (!el) return
        let frame = 0
        const measure = () => {
          cancelAnimationFrame(frame)
          frame = requestAnimationFrame(() => {
            const left = rootRef.current ? rootRef.current.getBoundingClientRect().left : 0
            setSidebarOpen(left > 140)
          })
        }
        measure()
        const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null
        if (observer) observer.observe(el)
        window.addEventListener('resize', measure)
        const timer = window.setInterval(measure, 600)
        return () => {
          cancelAnimationFrame(frame)
          if (observer) observer.disconnect()
          window.removeEventListener('resize', measure)
          window.clearInterval(timer)
        }
      }, [])
      // The supervisor answers even while the engine is still being prepared,
      // which is exactly when the page needs to explain what is happening.
      useEffect(() => {
        let alive = true
        const load = async () => { const next = await hostStatus(); if (alive) setEngine(next) }
        void load()
        const timer = setInterval(load, 2500)
        return () => { alive = false; clearInterval(timer) }
      }, [])
      useEffect(() => {
        if (!selected || (selected.status !== 'running' && selected.status !== 'queued')) return
        const timer = setInterval(async () => {
          try { const d = await api('/runs/' + selected.id); setSelected(d.run); setRuns(prev => prev.map(x => x.id === d.run.id ? d.run : x)) } catch (e) { if (!isTransientNetworkError(e)) setErr(String(e.message || e)) }
        }, 2000)
        return () => clearInterval(timer)
      }, [selected && selected.id, selected && selected.status])

      // One catalogue, two views: generation pages filter on kind + capability.
      const videoModels = (models || []).filter((m) => m.kind === 'video')

      const openRun = (run) => { setSelected(run) }
      const started = (run) => { setSelected(run); void refresh() }

      // First run, or a required dependency disappeared later: show the setup
      // page instead of letting a run fail at the first ffprobe call.
      const preflight = (engine && engine.preflight) || null
      const setupState = (preflight && preflight.state) || { doneAt: null, skippedAt: null }
      const blockedCount = preflight ? (preflight.blocking || []).length : 0
      // `checkedAt` is empty for the first few hundred ms after the Host starts.
      const checking = Boolean(preflight && !preflight.checkedAt && !setupState.doneAt && !setupState.skippedAt)
      const needsSetup = Boolean(forceSetup || checking || (preflight && !setupState.skippedAt && (!setupState.doneAt || blockedCount > 0)))

      const applySetup = (data) => {
        if (!data) return
        setEngine((prev) => {
          const base = Object.assign({}, prev || {})
          const next = Object.assign({}, base.preflight || {}, data.preflight || {})
          if (data.setup) next.state = data.setup
          base.preflight = next
          return base
        })
      }
      const setupRecheck = async () => {
        setSetupBusy('recheck'); setErr('')
        try { applySetup(await api('/setup/recheck', { method: 'POST' })) } catch (e) { setErr(String(e.message || e)) } finally { setSetupBusy('') }
      }
      const setupStart = async () => {
        setSetupBusy('start'); setErr('')
        try { applySetup(await api('/setup/state', { method: 'POST', body: { done: true } })); setForceSetup(false); await refresh() } catch (e) { setErr(String(e.message || e)) } finally { setSetupBusy('') }
      }
      const setupSkip = async () => {
        setSetupBusy('skip'); setErr('')
        try { applySetup(await api('/setup/state', { method: 'POST', body: { skip: true } })); setForceSetup(false) } catch (e) { setErr(String(e.message || e)) } finally { setSetupBusy('') }
      }

      return h('div', { ref: rootRef, className: 'adp-root' + (IS_MAC ? ' adp-mac' : '') + (IS_MAC && sidebarOpen ? ' adp-sidebar-open' : '') },
        h('style', null, CSS),
        h('div', { className: 'adp-top' },
          h('div', { className: 'adp-brand' }, 'AdClip'),
          h('div', { className: 'adp-sub' }, 'AI AD VIDEO STUDIO'),
          h('div', { className: 'adp-tabs', style: needsSetup ? { visibility: 'hidden' } : null },
            ['recreate', 'text', 'assets', 'personas', 'tasks', 'settings'].map(id => h('button', { key: id, className: 'adp-tab' + (tab === id ? ' on' : ''), onClick: () => { setTab(id); setSelected(null) } }, { recreate: '爆款复刻', text: '自由创作', assets: '素材', personas: '模特', tasks: '任务', settings: '设置' }[id]))
          ),
          h('div', { className: 'adp-grow' }),
          engine
            ? h(Badge, { status: engine.ok ? 'ok' : ((engine.boot && engine.boot.stage === 'preparing') ? 'warn' : 'bad') }, engine.ok ? '引擎在线' : '引擎' + engineStageLabel(engine))
            : (health ? h(Badge, { status: health.ok ? 'ok' : 'bad' }, health.ok ? '引擎在线' : '引擎离线') : h(Badge, null, '连接中…'))
        ),
        h('div', { className: 'adp-body' },
          needsSetup
            ? h(SetupPage, { preflight, engine, busy: setupBusy, onRecheck: setupRecheck, onStart: setupStart, onSkip: setupSkip })
            : h('div', { className: 'adp-wrap' },
            engine && !engine.ok && engine.boot && (engine.boot.stage === 'preparing' || engine.boot.stage === 'failed')
              ? h('div', { className: engine.boot.stage === 'failed' ? 'adp-error' : 'adp-notice', style: { marginBottom: 10 } },
                  engine.boot.stage === 'preparing'
                    ? '引擎准备中：' + (engine.boot.detail || '正在安装 Python 依赖')
                    : '引擎不可用：' + (engine.boot.detail || '未知原因') + '（可到「设置」里点「重新启动引擎」）'
                )
              : null,
            err ? h('div', { className: 'adp-error' }, err) : null,
            blockedCount > 0 && !needsSetup
              ? h('div', { className: 'adp-notice', style: { marginBottom: 10 } },
                  '运行环境缺少 ' + blockedCount + ' 项，相关功能不可用。',
                  h('button', { className: 'adp-btn ghost', style: { marginLeft: 8 }, onClick: () => setForceSetup(true) }, '去处理'))
              : null,
            selected ? h(ResultPanel, { run: selected, onChanged: started, onBack: () => setSelected(null), assets }) : null,
            h('div', { style: { display: (!selected && tab === 'recreate') ? 'block' : 'none' } }, h(RecreateTab, { models: videoModels, onStarted: started, personas, onRefreshPersonas: refresh })),
            h('div', { style: { display: (!selected && tab === 'text') ? 'block' : 'none' } }, h(TextTab, { dsh, textModels, onStarted: started, onRefreshAssets: refresh })),
            !selected && tab === 'assets' ? h(AssetsTab, { onRefresh: refresh }) : null,
            !selected && tab === 'personas' ? h(PersonasTab, { personas, onRefresh: refresh }) : null,
            !selected && tab === 'tasks' ? h(TasksTab, { onOpen: openRun }) : null,
            !selected && tab === 'settings' ? h(SettingsTab, { health, models, assets, textModels, scheduling, onRefresh: refresh, engine, onSetup: () => setForceSetup(true) }) : null,
          )
        )
      )
    }

    return {
      inject: ['slots'],
      apply(ctx) {
        ctx.slots.inject('main', () => ctx.slots.register({ name: 'main', key: 'adplus' }, () => h(AdClipBoundary, null, h(App))))
        ctx.slots.inject('sidebar.panellist', () => ctx.slots.register({ name: 'sidebar.panellist', id: 'adplus', order: 30, label: () => 'AdClip' }, Icon))
      },
    }
  },
})
