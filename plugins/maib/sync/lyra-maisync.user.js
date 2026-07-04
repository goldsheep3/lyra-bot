// ==UserScript==
// @name         Lyra Mai Sync (Beta)
// @description  用于捕获「电棍」版本的舞萌数据 - 重构版 [RC]
// @version      0.3.0-rc2
// @author       GoldSheep3 with Gemini
// @match        https://*/maimai/music
// @match        https://*/maimai/music?*
// @updateURL    https://github.com/goldsheep3/lyra-parse/raw/refs/heads/main/monkey/lyra-mai.user.js
// @downloadURL  https://github.com/goldsheep3/lyra-parse/raw/refs/heads/main/monkey/lyra-mai.user.js
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_deleteValue
// @grant        GM_download
// @require      https://cdn.jsdelivr.net/npm/pako@2.1.0/dist/pako.min.js
// ==/UserScript==

// =============== 🔧 配置区域 (可修改) ===============
const CONFIG = {
    // 🔹 调试模式: true=显示日志, false=静默运行
    DEBUG: true,
    
    // 🔹 脚本版本标识（仅用于日志）
    VERSION: '0.3.0-rc2',
    
    // 🔹 存储键名
    STORE_KEY: 'lyra_mai_multistore',
    
    // 🔹 目标 ID 范围
    ID_MIN: 1,
    ID_MAX: 99,
    
    // 🔹 超时设置 (毫秒)
    TIMEOUT_SCROLL: 4000,      // 滚动加载等待
    TIMEOUT_PAGE: 6000,        // 页面切换等待
    TIMEOUT_VERIFY: 3000,      // 页面验证等待
    TIMEOUT_STORAGE: 2000,     // 存储验证等待
    
    // 🔹 滚动参数
    SCROLL_STEP: 1500,         // 每次滚动像素
    SCROLL_INTERVAL: 200,      // 滚动间隔毫秒
    SCROLL_STABLE_COUNT: 2,    // 稳定判定次数
    
    // 🔹 UI 样式配置
    STYLES: {
        BTN: "padding:7px 14px;color:#fff;border:none;border-radius:8px;cursor:pointer;font-weight:600;font-size:13px;transition:all 0.15s;",
        BTN_SM: "padding:6px 10px;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:500;font-size:12px;",
        PANEL: "position:fixed;bottom:20px;left:50%;transform:translateX(-50%);z-index:10000;display:flex;gap:6px;align-items:center;background:rgba(255,255,255,0.98);padding:8px 12px;border:1px solid rgba(0,0,0,0.08);border-radius:12px;box-shadow:0 4px 16px rgba(0,0,0,0.15);",
        MODAL_BG: "position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.45);z-index:20000;display:flex;align-items:center;justify-content:center;",
        MODAL_BOX: "background:#fff;padding:18px 22px;border-radius:14px;min-width:300px;max-width:460px;box-shadow:0 6px 24px rgba(0,0,0,0.22);",
        BADGE: "background:linear-gradient(135deg,#e84393,#fd79a8);color:#fff;padding:5px 10px;border-radius:8px;font-weight:800;font-size:13px;",
    },
    
    // 🔹 按钮颜色配置
    COLORS: {
        CATCH: '#00b8a9',      // 捕获按钮
        EXPORT: '#3775de',     // 导出按钮
        MORE: '#7f8c8d',       // 更多按钮
        STOP: '#e74c3c',       // 停止按钮
        NEXT: '#3498db',       // 下一页按钮
        DX: '#34495e',         // dxrating 导出
        GZIP: '#9b59b6',       // gzip 导出
        CLEAR: '#e74c3c',      // 清除数据
        CANCEL: '#95a5a6',     // 取消按钮
        CONFIRM: '#27ae60',    // 确认按钮
    },
    
    // 🔹 导出文件名模板
    EXPORT_NAMES: {
        DX: (id) => `lyra-dx-id${id}.json`,
        GZIP: (id) => `lyra-gz-id${id}.json.gz.b64`,
    },
};

// =============== 🔧 配置区域结束 ===============

(function() {
    'use strict';

    // 从 CONFIG 解构常用项
    const { DEBUG, VERSION, STORE_KEY, ID_MIN, ID_MAX, TIMEOUT_SCROLL, TIMEOUT_PAGE, 
            TIMEOUT_VERIFY, TIMEOUT_STORAGE, SCROLL_STEP, SCROLL_INTERVAL, SCROLL_STABLE_COUNT, 
            STYLES, COLORS, EXPORT_NAMES } = CONFIG;

    const MAI_SYNC_DESC_HEADER = 'lyra_maisync:json.gz.base64:v0.3.0;';
    
    const LOG = (...args) => { if (DEBUG) console.log('[LyraMai]', ...args); };
    const WARN = (...args) => console.warn('[LyraMai⚠️]', ...args);
    const ERR = (...args) => console.error('[LyraMai❌]', ...args);

    const multiDataStore = {};
    let currentTargetId = 1;
    let isCapturing = false;

    // =============== 工具函数 ===============

    const parseTimeToTimestamp = (timeStr) => {
        if (!timeStr) return 0;
        try {
            let date;
            if (timeStr.includes('T') || timeStr.includes('Z')) {
                date = new Date(timeStr);
            } else if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(timeStr)) {
                const [d, t] = timeStr.split(' ');
                const [y, m, day] = d.split('-').map(Number);
                const [h, min, s] = t.split(':').map(Number);
                date = new Date(y, m - 1, day, h, min, s);
            } else {
                date = new Date(timeStr);
            }
            const ts = date.getTime();
            return isNaN(ts) ? 0 : Math.floor(ts / 1000);
        } catch (e) {
            WARN('时间解析失败:', timeStr, e);
            return 0;
        }
    };

    const getImgName = (src) => {
        if (!src) return "";
        let name = src.split('/').pop().replace(/\.[^/.]+$/, "");
        name = name.replace('music_icon_', '').replace('music_', '').replace('diff_', '');
        return name === 'standard' ? 'std' : name;
    };

    const generateSheetId = (title, type, diff) => `${title}__dxrt__${type}__dxrt__${diff}`;

    const parseAchievement = (rawStr) => {
        if (!rawStr) return 0;
        const str = rawStr.trim();
        const cleaned = str.replace(/\s+/g, '');
        const match = cleaned.match(/^(\d+\.?\d*)%?$/);
        if (match) return parseFloat(match[1]);
        const digits = cleaned.replace(/[^\d.]/g, '');
        return parseFloat(digits) || 0;
    };

    const waitForScrollLoad = async (timeoutMs = TIMEOUT_SCROLL) => {
        const start = Date.now();
        let lastH = 0, stable = 0;
        while (Date.now() - start < timeoutMs) {
            await new Promise(r => setTimeout(r, SCROLL_INTERVAL));
            const h = document.documentElement.scrollHeight;
            if (h === lastH) { if (++stable >= SCROLL_STABLE_COUNT) return true; }
            else { stable = 0; lastH = h; }
        }
        return true;
    };

    const waitForPageLoad = async (timeoutMs = TIMEOUT_PAGE) => {
        LOG('🔄 等待新页面加载, timeout:', timeoutMs);
        const start = Date.now();
        while (Date.now() - start < timeoutMs) {
            await new Promise(r => setTimeout(r, 300));
            const boxes = document.querySelectorAll('.mai-music-box');
            if (boxes.length > 0) {
                LOG('✅ 新页面元素已加载, 数量:', boxes.length);
                return true;
            }
        }
        LOG('⏰ 页面加载超时');
        return false;
    };

    const getNextPageButton = () => {
        LOG('🔍 查找下一页按钮...');
        const activePage = document.querySelector('.n-pagination-item--active');
        if (activePage) {
            const currentPage = parseInt(activePage.innerText.trim());
            LOG('📄 当前页码:', currentPage);
            const nextPageBtn = Array.from(document.querySelectorAll('.n-pagination-item--clickable'))
                .find(el => {
                    const txt = el.innerText.trim();
                    return txt === String(currentPage + 1) && !isNaN(currentPage);
                });
            if (nextPageBtn) {
                LOG('✅ 找到下一页数字按钮:', currentPage + 1);
                return nextPageBtn;
            }
        }
        const arrowButtons = Array.from(document.querySelectorAll('.n-pagination-item.n-pagination-item--button'))
            .filter(btn => !btn.classList.contains('n-pagination-item--disabled'));
        if (arrowButtons.length === 2) {
            LOG('✅ 找到右侧箭头按钮 (2个可用箭头)');
            return arrowButtons[1];
        } else if (arrowButtons.length === 1) {
            const svg = arrowButtons[0].querySelector('svg path');
            if (svg && svg.getAttribute('d')?.startsWith('M7.')) {
                LOG('✅ 找到右侧箭头按钮 (SVG 方向验证)');
                return arrowButtons[0];
            }
        }
        LOG('⚠️ 未找到明确的下一页按钮');
        return null;
    };

    const verifyPageChanged = async (prevFirstRecord, timeoutMs = TIMEOUT_VERIFY) => {
        LOG('🔍 验证页面是否切换...');
        const start = Date.now();
        while (Date.now() - start < timeoutMs) {
            await new Promise(r => setTimeout(r, 200));
            const firstBox = document.querySelector('.mai-music-box');
            if (firstBox) {
                const titleEl = firstBox.querySelector('.mai-music-title');
                const title = titleEl?.innerText?.trim();
                const timeEl = firstBox.querySelector('.sub_title span:last-child');
                const time = timeEl?.innerText?.trim();
                const currentKey = `${title}_${time}`;
                if (currentKey && currentKey !== prevFirstRecord) {
                    LOG('✅ 页面已切换, 新记录:', currentKey);
                    return true;
                }
                LOG('⏳ 页面内容未变化, 等待中...');
            }
        }
        LOG('⚠️ 页面切换验证超时');
        return false;
    };

    // dxrating 导出前去重 - 相同 sheetId 取最高 achievementRate
    const dedupeForDxRating = (records) => {
        LOG('🔀 开始 dxrating 去重处理...');
        const bestMap = new Map();
        records.forEach(rec => {
            const existing = bestMap.get(rec.sheetId);
            if (!existing || rec.achievementRate > existing.achievementRate) {
                bestMap.set(rec.sheetId, rec);
                LOG('📈 更新最优记录:', rec.sheetId, '@', rec.achievementRate);
            }
        });
        const result = Array.from(bestMap.values());
        LOG(`✅ 去重完成: ${records.length} → ${result.length} 条`);
        return result;
    };

    // =============== 存储验证 ===============

    const verifyStorage = async (key, expectedValue, timeoutMs = TIMEOUT_STORAGE) => {
        LOG('🔐 验证存储:', key);
        return new Promise((resolve) => {
            const start = Date.now();
            const check = () => {
                const val = GM_getValue(key);
                const match = JSON.stringify(val) === JSON.stringify(expectedValue);
                if (match) {
                    LOG('✅ 存储验证成功');
                    resolve(true);
                } else if (Date.now() - start >= timeoutMs) {
                    WARN('❌ 存储验证超时/失败');
                    resolve(false);
                } else {
                    setTimeout(check, 100);
                }
            };
            setTimeout(check, 50);
        });
    };

    // =============== 数据解析 ===============

    const parseVisibleRecords = () => {
        LOG('🔍 开始解析可见记录...');
        const records = [];
        
        document.querySelectorAll('.mai-music-box').forEach((node, idx) => {
            const titleEl = node.querySelector('.mai-music-title');
            const title = titleEl?.innerText?.trim() || titleEl?.textContent?.trim();
            if (!title) return;
            
            const type = getImgName(node.querySelector('.playlog_music_kind_icon')?.src);
            const diff = getImgName(node.querySelector('#diff_and_date img')?.src);
            const achEl = node.querySelector('.mai-music-info_achievement_score');
            const achRaw = achEl?.innerText || achEl?.textContent || "0";
            const achievement = parseAchievement(achRaw);
            
            let dxscore = 0;
            const dxEl = node.querySelector('.mai-music-info_dx_score') || node.querySelector('.score');
            if (dxEl) {
                const dxStr = dxEl.innerText.split('/')[0]?.trim();
                dxscore = parseInt(dxStr) || 0;
            }
            
            const badges = Array.from(node.querySelectorAll('.playlog_score'));
            const combo = getImgName(badges[0]?.src), sync = getImgName(badges[1]?.src);
            const timeEl = node.querySelector('.sub_title span:last-child');
            const play_time = parseTimeToTimestamp(timeEl?.innerText?.trim());
            
            records.push({
                sheetId: generateSheetId(title, type, diff),
                achievementRate: achievement, title, type, diff,
                achievement, dxscore, combo, sync, play_time
            });
        });

        document.querySelectorAll('.music_list_item').forEach(node => {
            const title = node.querySelector('.music_name_block')?.innerText?.trim();
            if (!title) return;
            const type = getImgName(node.querySelector('.music_kind_icon')?.src);
            const diff = getImgName(node.querySelector('img[src*="diff_"]')?.src);
            const achRaw = node.querySelector('.music_score_block')?.innerText || "0";
            const achievement = parseAchievement(achRaw);
            const dxscore = parseInt(node.querySelector('.music_score_block span')?.innerText?.trim()) || 0;
            const imgs = Array.from(node.querySelectorAll('.music_rate_block img'));
            
            records.push({
                sheetId: generateSheetId(title, type, diff),
                achievementRate: achievement, title, type, diff,
                achievement, dxscore,
                combo: getImgName(imgs[1]?.src),
                sync: getImgName(imgs[2]?.src),
                play_time: 0
            });
        });

        LOG(`✅ 解析完成: 总计 ${records.length} 条`);
        return records;
    };

    // =============== 存储管理 ===============

    const loadStore = () => {
        const raw = GM_getValue(STORE_KEY, {});
        if (raw && typeof raw === 'object') {
            Object.keys(raw).forEach(k => { const id = parseInt(k); if (!isNaN(id)) multiDataStore[id] = raw[k]; });
        }
        if (!multiDataStore[currentTargetId]) multiDataStore[currentTargetId] = [];
    };

    const saveStore = async () => {
        LOG('💾 保存存储, ID#', currentTargetId, '长度:', getCurrentArray().length);
        GM_setValue(STORE_KEY, multiDataStore);
        const ok = await verifyStorage(STORE_KEY, multiDataStore);
        if (!ok) WARN('⚠️ 存储验证失败，建议刷新页面重试');
        return ok;
    };

    const getCurrentArray = () => { if (!multiDataStore[currentTargetId]) multiDataStore[currentTargetId] = []; return multiDataStore[currentTargetId]; };

    const isRecordExists = (targetArr, sheetId, play_time) => {
        return targetArr.some(r => r.sheetId === sheetId && r.play_time === play_time);
    };

    // =============== 核心逻辑 ===============

    const processCurrentPage = async () => {
        LOG('🔄 处理当前页...');
        const target = getCurrentArray();
        let cnt = 0, dup = 0;
        const rawRecords = parseVisibleRecords();
        
        rawRecords.forEach(rec => {
            if (isRecordExists(target, rec.sheetId, rec.play_time)) {
                LOG('🌐 存储中已存在，跳过:', `${rec.sheetId}_${rec.play_time}`);
                dup++;
                return;
            }
            target.push(rec);
            cnt++;
        });
        
        await saveStore();
        LOG(`📈 本页结果: 新增 ${cnt}, 重复 ${dup}, 总计 ${target.length}`);
        return cnt;
    };

    const capturePage = async () => {
        LOG('🎬 开始捕获单页');
        window.scrollTo(0, 0);
        await waitForScrollLoad();
        
        let lastH = 0, stable = 0;
        while (stable < SCROLL_STABLE_COUNT) {
            window.scrollBy(0, SCROLL_STEP);
            await new Promise(r => setTimeout(r, SCROLL_INTERVAL));
            const h = document.documentElement.scrollHeight;
            if (h === lastH) stable++; else { stable = 0; lastH = h; }
        }
        return await processCurrentPage();
    };

    // =============== UI 组件 ===============

    const createPanel = () => {
        if (document.getElementById('lyra-panel')) return;
        const p = document.createElement('div'); p.id = 'lyra-panel'; p.style = STYLES.PANEL;
        
        const badge = document.createElement('div'); badge.innerText = 'mai'; badge.style = STYLES.BADGE; p.appendChild(badge);
        
        const btnCatch = document.createElement('button'); btnCatch.innerText = '捕获'; btnCatch.style = STYLES.BTN + `background:${COLORS.CATCH};`;
        btnCatch.onclick = () => showIdModal(true); p.appendChild(btnCatch);
        
        const btnExport = document.createElement('button'); btnExport.innerText = '导出'; btnExport.style = STYLES.BTN + `background:${COLORS.EXPORT};`;
        btnExport.onclick = () => showExportModal(); p.appendChild(btnExport);
        
        const btnMore = document.createElement('button'); btnMore.innerText = '更多'; btnMore.style = STYLES.BTN + `background:${COLORS.MORE};`;
        btnMore.onclick = (e) => { e.stopPropagation(); toggleMoreMenu(moreMenu); };
        p.appendChild(btnMore);
        
        const moreMenu = document.createElement('div');
        moreMenu.style = "position:absolute;bottom:calc(100% + 8px);right:0;background:#fff;padding:8px;border-radius:10px;box-shadow:0 4px 16px rgba(0,0,0,0.18);display:none;flex-direction:column;gap:6px;min-width:140px;z-index:10001;";
        moreMenu.innerHTML = `
            <button style="${STYLES.BTN_SM}background:${COLORS.DX};text-align:left;">📖 使用说明</button>
            <button id="lyra-more-import" style="${STYLES.BTN_SM}background:${COLORS.GZIP};text-align:left;">📥 导入数据</button>
            <button id="lyra-more-clear" style="${STYLES.BTN_SM}background:${COLORS.CLEAR};text-align:left;">🗑️ 清除数据</button>
        `;
        p.appendChild(moreMenu);
        document.addEventListener('click', () => { moreMenu.style.display = 'none'; });
        
        document.body.appendChild(p);
    };

    const toggleMoreMenu = (menu) => { menu.style.display = menu.style.display === 'none' ? 'flex' : 'none'; };

    const showIdModal = (startCapture) => {
        if (isCapturing) return;
        const m = document.createElement('div'); m.style = STYLES.MODAL_BG;
        m.innerHTML = `
            <div style="${STYLES.MODAL_BOX}">
                <h4 style="margin:0 0 12px;font-size:15px;">选择目标 ID</h4>
                <p style="margin:0 0 14px;color:#666;font-size:13px;">不同 ID 的数据相互隔离</p>
                <div style="display:flex;gap:8px;align-items:center;margin-bottom:16px;">
                    <span style="font-size:13px;">ID:</span>
                    <input type="number" id="lyra-id-inp" value="${currentTargetId}" min="${ID_MIN}" max="${ID_MAX}" style="width:70px;padding:6px 10px;border:1px solid #ddd;border-radius:6px;font-size:13px;">
                </div>
                <div style="display:flex;gap:8px;justify-content:flex-end;">
                    <button id="lyra-id-cancel" style="${STYLES.BTN}background:${COLORS.CANCEL};">取消</button>
                    <button id="lyra-id-ok" style="${STYLES.BTN}background:${COLORS.CONFIRM};">确认</button>
                </div>
            </div>`;
        document.body.appendChild(m);
        const go = () => {
            const v = parseInt(document.getElementById('lyra-id-inp').value);
            if (v >= ID_MIN && v <= ID_MAX) { currentTargetId = v; loadStore(); if (startCapture) doCapture(); }
            cleanup();
        };
        const cleanup = () => {
            document.getElementById('lyra-id-ok')?.removeEventListener('click', go);
            document.getElementById('lyra-id-cancel')?.removeEventListener('click', cleanup);
            m.remove();
        };
        document.getElementById('lyra-id-ok')?.addEventListener('click', go);
        document.getElementById('lyra-id-cancel')?.addEventListener('click', cleanup);
        m.addEventListener('click', e => { if (e.target === m) cleanup(); });
    };

    const doCapture = async () => {
        LOG('🚀 开始捕获流程');
        isCapturing = true;
        loadStore();
        const cnt = await capturePage();
        LOG('🎉 捕获完成, 新增:', cnt);
        showResultModal(cnt);
    };

    const showResultModal = (newCnt) => {
        LOG('🪟 显示结果弹窗, newCnt:', newCnt);
        const m = document.createElement('div'); m.style = STYLES.MODAL_BG;
        const hasNext = newCnt > 0;
        m.innerHTML = `
            <div style="${STYLES.MODAL_BOX}">
                <h4 style="margin:0 0 10px;font-size:15px;">ID#${currentTargetId} · 捕获完成</h4>
                <p style="margin:0 0 14px;color:#555;font-size:13px;">
                    本页新增: <strong style="color:#27ae60;">${newCnt}</strong> | 总计: <strong>${getCurrentArray().length}</strong>
                </p>
                <div style="display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap;">
                    <button id="lyra-res-stop" style="${STYLES.BTN}background:${COLORS.STOP};">停止</button>
                    ${hasNext ? `<button id="lyra-res-next" style="${STYLES.BTN}background:${COLORS.NEXT};">下一页</button>` : ''}
                    <button id="lyra-res-export" style="${STYLES.BTN}background:${COLORS.GZIP};">前往导出</button>
                </div>
            </div>`;
        document.body.appendChild(m);
        const cleanup = () => {
            document.getElementById('lyra-res-stop')?.removeEventListener('click', stopCap);
            document.getElementById('lyra-res-next')?.removeEventListener('click', goNext);
            document.getElementById('lyra-res-export')?.removeEventListener('click', goExport);
            m.remove();
        };
        const stopCap = () => { LOG('🛑 用户点击【停止】'); isCapturing = false; cleanup(); };
        
        const goNext = async () => {
            LOG('➡️ 用户点击【下一页】');
            cleanup();
            window.scrollTo(0, 0);
            await new Promise(r => setTimeout(r, 500));
            
            const firstBox = document.querySelector('.mai-music-box');
            const prevTitle = firstBox?.querySelector('.mai-music-title')?.innerText?.trim();
            const prevTime = firstBox?.querySelector('.sub_title span:last-child')?.innerText?.trim();
            const prevKey = `${prevTitle}_${prevTime}`;
            LOG('📋 当前页标识:', prevKey);
            
            const nextBtn = getNextPageButton();
            if (nextBtn) {
                LOG('🔘 点击下一页按钮');
                nextBtn.click();
                const loaded = await waitForPageLoad();
                if (!loaded) {
                    WARN('❌ 页面加载超时');
                    alert('页面加载超时，请手动刷新后重试');
                    isCapturing = false;
                    return;
                }
                const changed = await verifyPageChanged(prevKey);
                if (changed) {
                    LOG('✅ 页面切换验证成功，继续捕获');
                    await doCapture();
                } else {
                    WARN('❌ 页面未成功切换，可能已是最后一页');
                    alert('未检测到页面变化，可能已是最后一页');
                    isCapturing = false;
                }
            } else {
                WARN('❌ 未找到下一页按钮');
                alert('未找到下一页按钮，可能已是最后一页');
                isCapturing = false;
            }
        };
        
        const goExport = () => { LOG('📤 用户点击【前往导出】'); cleanup(); showExportModal(); };
        
        document.getElementById('lyra-res-stop')?.addEventListener('click', stopCap);
        if (hasNext) document.getElementById('lyra-res-next')?.addEventListener('click', goNext);
        document.getElementById('lyra-res-export')?.addEventListener('click', goExport);
        m.addEventListener('click', e => { if (e.target === m) stopCap(); });
    };

    const showExportModal = () => {
        LOG('🪟 显示导出弹窗');
        const m = document.createElement('div'); m.style = STYLES.MODAL_BG;
        m.innerHTML = `
            <div style="${STYLES.MODAL_BOX}">
                <h4 style="margin:0 0 10px;font-size:15px;">导出 · ID#${currentTargetId}</h4>
                <p style="margin:0 0 14px;color:#666;font-size:13px;">共 <strong>${getCurrentArray().length}</strong> 条</p>
                <div style="display:flex;flex-direction:column;gap:8px;">
                    <button id="lyra-exp-dx" style="${STYLES.BTN}background:${COLORS.DX};text-align:left;">📊 dxrating.net 导入</button>
                    <button id="lyra-exp-gz" style="${STYLES.BTN}background:${COLORS.GZIP};text-align:left;">🗜️ gzip 压缩备份</button>
                    <button id="lyra-exp-up" style="${STYLES.BTN}background:${COLORS.MORE};text-align:left;opacity:0.7;" disabled>☁️ 在线上传 (预留)</button>
                    <button id="lyra-exp-cancel" style="${STYLES.BTN}background:${COLORS.CANCEL};">取消</button>
                </div>
            </div>`;
        document.body.appendChild(m);
        const cleanup = () => m.remove();
        
        document.getElementById('lyra-exp-dx')?.addEventListener('click', () => {
            LOG('📊 导出 dxrating 格式');
            const deduped = dedupeForDxRating(getCurrentArray());
            const arr = deduped.map(r => ({ sheetId: r.sheetId, achievementRate: r.achievementRate }));
            LOG('📦 导出数据预览:', arr.slice(0, 3));
            download(EXPORT_NAMES.DX(currentTargetId), JSON.stringify(arr, null, 2)); cleanup();
        });
        
        // gzip 导出使用 Base64+普通下载，兼容所有浏览器
        document.getElementById('lyra-exp-gz')?.addEventListener('click', async () => {
            LOG('🗜️ 导出 gzip 压缩格式');
            try {
                const json = JSON.stringify(getCurrentArray());
                const gzipped = pako.gzip(json, { level: 9 });
                LOG('📦 原始大小:', json.length, '→ 压缩后:', gzipped.length, `(${Math.round(gzipped.length/json.length*100)}%)`);
                
                // Uint8Array → Binary String → Base64
                let binary = '';
                for (let i = 0; i < gzipped.length; i++) {
                    binary += String.fromCharCode(gzipped[i]);
                }

                const base64 = btoa(binary);
                const payload = MAI_SYNC_DESC_HEADER + base64;
                const ok = download(EXPORT_NAMES.GZIP(currentTargetId), payload);

                if (ok) {
                    LOG('✅ gzip 导出成功 (Base64 格式)');
                    alert(`导出成功!\n📁 ${EXPORT_NAMES.GZIP(currentTargetId)}\n📊 ${getCurrentArray().length} 条记录\n💡 文件名含 .b64，导入时请移除该后缀`);
                } else {
                    WARN('❌ 下载失败');
                    alert('下载失败，请检查浏览器是否拦截弹窗');
                }
            } catch (e) {
                ERR('gzip 导出异常:', e);
                alert('压缩导出失败: ' + e.message);
            }
            cleanup();
        });
        
        document.getElementById('lyra-exp-cancel')?.addEventListener('click', cleanup);
        m.addEventListener('click', e => { if (e.target === m) cleanup(); });
    };

    // 普通下载函数，返回是否成功
    const download = (name, content) => {
        try {
            LOG('💾 下载文件:', name, '大小:', content.length);
            const blob = new Blob([content], { type: 'application/octet-stream' });
            const url = URL.createObjectURL(blob), a = document.createElement('a');
            a.href = url; a.download = name; document.body.appendChild(a); a.click();
            document.body.removeChild(a); URL.revokeObjectURL(url);
            LOG('✅ 下载触发成功');
            return true;
        } catch (e) {
            ERR('❌ 下载异常:', e);
            return false;
        }
    };

    // =============== 更多菜单功能 ===============

    const showUsage = () => {
        const m = document.createElement('div'); m.style = STYLES.MODAL_BG;
        m.innerHTML = `
            <div style="${STYLES.MODAL_BOX}">
                <h4 style="margin:0 0 12px;">使用说明</h4>
                <ul style="margin:0 0 16px;padding-left:18px;color:#555;font-size:13px;line-height:1.6;">
                    <li>点击【捕获】→ 输入 ID → 自动滚动加载当前页</li>
                    <li>捕获结束后：可【下一页】继续 /【前往导出】/【停止】</li>
                    <li>【导出】支持 dxrating 格式 / gzip 压缩备份</li>
                    <li>dxrating 导出会自动去重，相同曲目取最高达成率</li>
                    <li>gzip 备份使用 pako 库压缩，体积更小，文件名为 .b64 后缀</li>
                    <li>导入 gzip 备份时，请先移除文件名末尾的 .b64</li>
                    <li>【更多】→【清除数据】需手动输入 ID 确认</li>
                </ul>
                <button onclick="this.closest('.lyra-modal')?.remove()" style="${STYLES.BTN}background:${COLORS.CONFIRM};width:100%;">知道了</button>
            </div>`;
        m.className = 'lyra-modal'; document.body.appendChild(m);
        m.querySelector('button')?.addEventListener('click', () => m.remove());
        m.addEventListener('click', e => { if (e.target === m) m.remove(); });
    };

    const showImportHint = () => alert('该版本暂不支持导入功能');

    const showClearConfirm = () => {
        LOG('🗑️ 显示清除确认弹窗');
        const m = document.createElement('div'); m.style = STYLES.MODAL_BG;
        m.innerHTML = `
            <div style="${STYLES.MODAL_BOX}">
                <h4 style="margin:0 0 12px;color:${COLORS.CLEAR};">⚠️ 清除数据</h4>
                <p style="margin:0 0 8px;font-size:13px;color:#555;">请输入要清除的 ID 数字 (${ID_MIN}-${ID_MAX})<br><small style="color:#999;">此操作不可恢复</small></p>
                <input type="number" id="lyra-clear-inp" min="${ID_MIN}" max="${ID_MAX}" placeholder="输入 ID" style="width:100%;padding:8px 12px;border:1px solid #ddd;border-radius:6px;font-size:14px;margin-bottom:8px;">
                <div id="lyra-clear-count" style="margin:0 0 12px;font-size:12px;color:#666;display:none;"></div>
                <div style="display:flex;gap:8px;justify-content:flex-end;">
                    <button id="lyra-clear-cancel" style="${STYLES.BTN}background:${COLORS.CANCEL};">取消</button>
                    <button id="lyra-clear-do" style="${STYLES.BTN}background:${COLORS.CLEAR};">确认清除</button>
                </div>
            </div>`;
        document.body.appendChild(m);
        
        const countEl = document.getElementById('lyra-clear-count');
        const inp = document.getElementById('lyra-clear-inp');
        const updateCount = () => {
            const id = parseInt(inp.value);
            if (id >= ID_MIN && id <= ID_MAX && multiDataStore[id]) {
                const cnt = multiDataStore[id].length;
                countEl.innerText = `📋 ID#${id} 当前有 ${cnt} 条历史记录`;
                countEl.style.display = 'block';
                LOG('📊 显示清除条数: ID#', id, '→', cnt, '条');
            } else {
                countEl.style.display = 'none';
            }
        };
        inp.addEventListener('input', updateCount);
        inp.addEventListener('change', updateCount);
        
        const cleanup = () => {
            inp.removeEventListener('input', updateCount);
            inp.removeEventListener('change', updateCount);
            m.remove();
        };
        
        document.getElementById('lyra-clear-do')?.addEventListener('click', () => {
            const id = parseInt(document.getElementById('lyra-clear-inp').value);
            LOG('🔢 用户输入清除 ID:', id);
            if (id >= ID_MIN && id <= ID_MAX && multiDataStore[id]) {
                const cnt = multiDataStore[id].length;
                if (confirm(`确定清除 ID#${id} 的 ${cnt} 条数据吗？\n此操作不可恢复`)) {
                    multiDataStore[id] = []; saveStore(); alert(`ID#${id} 已清空 (${cnt} 条)`);
                    LOG('🗑️ 已清除 ID#', id, '的', cnt, '条数据');
                }
            } else { alert(`请输入有效的 ID (${ID_MIN}-${ID_MAX})`); }
            cleanup();
        });
        document.getElementById('lyra-clear-cancel')?.addEventListener('click', cleanup);
        m.addEventListener('click', e => { if (e.target === m) cleanup(); });
    };

    // =============== 初始化 ===============

    const init = async () => {
        LOG('🔧 初始化脚本 v' + VERSION + ' [RC]');
        // 验证 pako 是否加载成功
        if (typeof pako === 'undefined' || typeof pako.gzip !== 'function') {
            WARN('❌ pako 库加载失败，gzip 导出功能不可用');
            alert('pako 库加载失败，请检查网络连接或刷新页面');
        } else {
            LOG('✅ pako 库加载成功');
        }
        loadStore();
        createPanel();
        setTimeout(() => {
            document.getElementById('lyra-more-import')?.addEventListener('click', (e) => { e.stopPropagation(); showImportHint(); });
            document.getElementById('lyra-more-clear')?.addEventListener('click', (e) => { e.stopPropagation(); showClearConfirm(); });
            document.querySelector('#lyra-panel button:first-of-type + button + button + div button:first-of-type')?.addEventListener('click', (e) => { e.stopPropagation(); showUsage(); });
        }, 100);
        LOG('✅ 初始化完成');
    };

    setTimeout(init, 1200);
})();
