        const basePath = location.pathname.replace(/\/$/, '');
        let backAction = null;

        const themeMap = {
            '--app-accent': '--primary-color',
            '--app-accent-text': '--text-primary-color',
            '--app-bg': '--primary-background-color',
            '--app-text': '--primary-text-color',
            '--app-text-secondary': '--secondary-text-color',
            '--app-card-bg': '--card-background-color',
            '--app-card-bg-hover': '--card-background-color',
            '--app-header-bg': '--card-background-color',
            '--app-border': '--divider-color',
            '--app-border-strong': '--divider-color'
        };

        const debugEl = document.getElementById('theme-debug');
        const debugPanel = document.getElementById('debug-panel');
        let debugEnabled = false;
        function debug(msg) {
            console.log('[dbg]', msg);
            if (debugEnabled && debugEl) {
                debugEl.textContent += msg + '\n';
                debugEl.scrollTop = debugEl.scrollHeight;
            }
        }
        function toggleDebug() {
            debugEnabled = !debugEnabled;
            debugPanel.style.display = debugEnabled ? 'flex' : 'none';
            debugEl.textContent = 'DBG-v7 app=v' + '__APP_VERSION__' + '\n';
            if (debugEnabled) applyTheme();
        }
        document.getElementById('title').addEventListener('click', toggleDebug);

        const debugTitle = document.getElementById('debug-title');
        debugTitle.addEventListener('mousedown', e => {
            if (e.target !== debugTitle) return;
            e.preventDefault();
            const rect = debugPanel.getBoundingClientRect();
            const offX = e.clientX - rect.left;
            const offY = e.clientY - rect.top;
            debugPanel.style.right = 'auto';
            function onMove(ev) {
                debugPanel.style.left = ev.clientX - offX + 'px';
                debugPanel.style.top = ev.clientY - offY + 'px';
            }
            function onUp() {
                window.removeEventListener('mousemove', onMove);
                window.removeEventListener('mouseup', onUp);
            }
            window.addEventListener('mousemove', onMove);
            window.addEventListener('mouseup', onUp);
        });

        function readVar(parentDoc, name) {
            try {
                const inline = parentDoc.documentElement.style.getPropertyValue(name).trim();
                if (inline) return inline;
                const el = parentDoc.createElement('div');
                el.style.cssText = 'position:fixed;color:var(' + name + ', inherit);';
                parentDoc.body.appendChild(el);
                const val = getComputedStyle(el).color;
                el.remove();
                return val && val !== 'rgba(0, 0, 0, 0)' ? val : '';
            } catch (e) {
                return '';
            }
        }

        function applyTheme() {
            if (window.parent === window) {
                return;
            }
            const root = document.documentElement;
            try {
                const parentDoc = window.parent.document;
                let applied = 0;
                for (const [target, sourceVar] of Object.entries(themeMap)) {
                    const val = readVar(parentDoc, sourceVar);
                    if (val) {
                        root.style.setProperty(target, val);
                        applied++;
                    }
                }
            } catch (e) {
                console.error('Could not apply HA theme:', e);
            }
        }

        applyTheme();
        setInterval(applyTheme, 1000);

        async function api(path) {
            const resp = await fetch(basePath + path);
            return resp.json();
        }

        function goBack() {
            if (backAction) backAction();
        }

        function setBack(action) {
            backAction = action;
            document.getElementById('back').style.display = action ? 'block' : 'none';
        }

        function showLoading() {
            document.getElementById('content').innerHTML = '<div class="loading"><div class="spinner"></div>Loading...</div>';
        }

        async function showHome() {
            beginView();
            setBack(null);
            setViewSpec(null);
            lastTable = null;
            usageViewActive = false;
            stopSettingsRefresh();
            document.getElementById('title').textContent = 'Home Assistant DB Manager';

            let html = '<div class="menu-section"><h2>Top-Usage</h2><div class="button-grid">';
            html += `<button class="nav-button" onclick="showUsageView('States', statesConfig)">States</button>`;
            html += `<button class="nav-button" onclick="showUsageView('Statistics', statisticsConfig)">Statistics</button>`;
            html += `<button class="nav-button" onclick="showUsageView('Statistics Short Term', statisticsShortTermConfig)">Statistics Short Term</button>`;
            html += `<button class="nav-button" onclick="showUsageView('Events', eventsConfig)">Events</button>`;
            html += '</div></div>';

            html += '<div class="menu-section"><h2>Tables</h2><div class="button-grid">';
            html += `<button class="nav-button" onclick="showTables()">All Tables</button>`;
            html += '</div></div>';

            html += '<div class="menu-section"><h2>Settings</h2><div class="button-grid">';
            html += `<button class="nav-button" onclick="showSettings()">Settings</button>`;
            html += '</div></div>';

            document.getElementById('content').innerHTML = html;
        }

        let usageData = [];
        let usageConfig = null;
        let usageSortKey = null;
        let usageSortDir = 'asc';

        const statesConfig = {
            listEndpoint: '/api/states',
            watchTable: 'states',
            label: 'entities',
            sortKey: 'entity_id',
            idKey: 'entity_id',
            childMaxKey: 'max_state_id',
            columns: [
                { key: 'entity_id', label: 'entity_id', click: v => `showEntityStates('${v}', 1)` },
                { key: 'metadata_id', label: 'metadata_id' },
                { key: 'state_count', label: 'state_count' },
                { key: '__new__', label: 'new' }
            ]
        };

        const statisticsConfig = {
            listEndpoint: '/api/statistics',
            watchTable: 'statistics',
            label: 'statistics',
            sortKey: 'statistic_id',
            idKey: 'statistic_id',
            childMaxKey: 'max_stat_id',
            columns: [
                { key: 'statistic_id', label: 'statistic_id', click: v => `showStatisticData('${v}', 1)` },
                { key: 'metadata_id', label: 'metadata_id' },
                { key: 'stat_count', label: 'stat_count' },
                { key: '__new__', label: 'new' }
            ]
        };

        const statisticsShortTermConfig = {
            listEndpoint: '/api/statistics-short-term',
            watchTable: 'statistics_short_term',
            label: 'short-term statistics',
            sortKey: 'statistic_id',
            idKey: 'statistic_id',
            childMaxKey: 'max_stat_id',
            columns: [
                { key: 'statistic_id', label: 'statistic_id', click: v => `showStatisticData('${v}', 1, '', '', true)` },
                { key: 'metadata_id', label: 'metadata_id' },
                { key: 'stat_count', label: 'stat_count' },
                { key: '__new__', label: 'new' }
            ]
        };

        const eventsConfig = {
            listEndpoint: '/api/event-types',
            watchTable: 'events',
            label: 'event types',
            sortKey: 'event_type',
            idKey: 'event_type',
            childMaxKey: 'max_event_id',
            columns: [
                { key: 'event_type', label: 'event_type', click: v => `showEventTypeData('${v}', 1)` },
                { key: 'event_type_id', label: 'event_type_id' },
                { key: 'event_count', label: 'event_count' },
                { key: '__new__', label: 'new' }
            ]
        };

        let usageGlobalBaseline = 0;
        let usageViewActive = false;

        function usageValue(e, key) {
            if (key === '__new__') return e['new_count'] || 0;
            return e[key];
        }

        async function usageReload() {
            if (!usageConfig) return;
            const gen = viewGen;
            try {
                const data = await api(usageConfig.listEndpoint + '?since=' + usageGlobalBaseline);
                if (!isCurrentView(gen) || !usageConfig) return;
                let changed = data.length !== usageData.length;
                if (!changed) {
                    for (let i = 0; i < data.length; i++) {
                        if ((data[i]['new_count'] || 0) !== (usageData[i]['new_count'] || 0)) {
                            changed = true;
                            break;
                        }
                    }
                }
                if (changed) {
                    usageData = data;
                    renderUsage();
                    const topNew = usageData
                        .map(e => ({
                            id: e[usageConfig.idKey],
                            max: e[usageConfig.childMaxKey],
                            new: e['new_count'] || 0
                        }))
                        .sort((a, b) => b.new - a.new)
                        .slice(0, 3);
                    debug(`usage reload '${usageConfig.label}' | top new: ` + JSON.stringify(topNew));
                }
            } catch (err) {}
        }

        async function showUsageView(title, config) {
            const gen = beginView();
            setBack(showHome);
            lastTable = null;
            usageViewActive = false;
            stopSettingsRefresh();
            document.getElementById('title').textContent = title;
            showLoading();
            usageData = await api(config.listEndpoint);
            if (!isCurrentView(gen)) return;
            usageConfig = config;
            usageSortKey = config.sortKey;
            usageSortDir = 'asc';
            usageGlobalBaseline = usageData.reduce((m, e) => Math.max(m, e[config.childMaxKey] || 0), 0);
            debug(`usage open '${title}': ${usageData.length} rows | globalBaseline=${usageGlobalBaseline} | sample ` +
                JSON.stringify(usageData.slice(0, 3).map(e => ({
                    id: e[config.idKey],
                    max: e[config.childMaxKey]
                }))));
            renderUsage();
            usageViewActive = true;
            setViewSpec({ kind: 'usage', table: config.watchTable, page: 1, page_size: 1, sort: null, dir: null });
        }

        function sortUsage(key) {
            if (usageSortKey === key) {
                usageSortDir = usageSortDir === 'asc' ? 'desc' : 'asc';
            } else {
                usageSortKey = key;
                usageSortDir = 'asc';
            }
            renderUsage();
        }

        function renderUsage() {
            const columns = usageConfig.columns;
            const sorted = [...usageData].sort((a, b) => {
                const va = usageValue(a, usageSortKey);
                const vb = usageValue(b, usageSortKey);
                const dir = usageSortDir === 'asc' ? 1 : -1;
                if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * dir;
                return String(va ?? '').localeCompare(String(vb ?? '')) * dir;
            });

            const arrow = usageSortDir === 'asc' ? ' &#9650;' : ' &#9660;';
            const thead = columns.map(c =>
                `<th style="cursor:pointer" onclick="sortUsage('${c.key}')">${c.label}${usageSortKey === c.key ? arrow : ''}</th>`
            ).join('');

            const rows = sorted.map(e => {
                let cells = '';
                for (const c of columns) {
                    const val = usageValue(e, c.key);
                    if (c.click && val != null) {
                        cells += `<td><a onclick="${c.click(val)}">${val}</a></td>`;
                    } else {
                        cells += `<td>${val != null ? val : ''}</td>`;
                    }
                }
                return '<tr>' + cells + '</tr>';
            }).join('');

            document.getElementById('content').innerHTML =
                `<div class="info">${usageData.length} ${usageConfig.label}</div>` +
                '<div class="container"><table><thead><tr>' + thead + '</tr></thead><tbody>' + rows + '</tbody></table></div>';
        }

        async function showTables() {
            const gen = beginView();
            setBack(showHome);
            setViewSpec(null);
            lastTable = null;
            usageViewActive = false;
            stopSettingsRefresh();
            document.getElementById('title').textContent = 'All Tables';
            showLoading();
            const tables = await api('/api/tables');
            if (!isCurrentView(gen)) return;
            const html = '<div class="table-list">' +
                tables.map(t => `<div class="table-card" onclick="showTable('${t}', 1)"><h3>${t}</h3></div>`).join('') +
                '</div>';
            document.getElementById('content').innerHTML = html;
        }

        function paginationHtml(data, pageCall) {
            return `<button onclick="${pageCall(data.page - 1)}" ${data.page <= 1 ? 'disabled' : ''}>&laquo; Prev</button>` +
                `<span>${data.page}</span>` +
                `<button onclick="${pageCall(data.page + 1)}" ${data.page >= data.total_pages ? 'disabled' : ''}>Next &raquo;</button>`;
        }

        function buildRows(data) {
            return data.rows.map(row => {
                let cells = '';
                data.columns.forEach(c => {
                    const raw = row[c] !== null ? row[c] : '';
                    const display = c.endsWith('_ts') ? formatTs(raw) : raw;
                    cells += `<td title="${String(raw).replace(/"/g, '&quot;')}">${display}</td>`;
                });
                return '<tr>' + cells + '</tr>';
            }).join('');
        }

        function buildThead(data, sort, sortAction) {
            let thead = '<tr>';
            data.columns.forEach(c => {
                const isSorted = sort && sort.key === c;
                const arrow = isSorted ? (sort.dir === 'asc' ? ' &#9650;' : ' &#9660;') : '';
                const onclick = sortAction
                    ? `onclick="${sortAction(c, isSorted && sort.dir === 'asc' ? 'desc' : 'asc')}"`
                    : '';
                thead += `<th style="cursor:pointer" ${onclick}>${c}${arrow}</th>`;
            });
            return thead + '</tr>';
        }

        function renderTablePage(data, pageCall, sort, sortAction, silentFetch) {
            lastTable = { data, pageCall, sort, sortAction, silentFetch };
            document.getElementById('content').innerHTML =
                `<div class="info" id="info-el">${data.total_rows} rows total | Page ${data.page} of ${data.total_pages}</div>` +
                `<div class="pagination" id="pag-top">${paginationHtml(data, pageCall)}</div>` +
                '<div class="container"><table><thead id="thead-el">' + buildThead(data, sort, sortAction) + '</thead>' +
                '<tbody id="tbody-el">' + buildRows(data) + '</tbody></table></div>' +
                `<div class="pagination" id="pag-bottom">${paginationHtml(data, pageCall)}</div>`;
        }

        function updateTableInPlace(data, pageCall) {
            if (!lastTable) return;
            lastTable.data = data;
            lastTable.pageCall = pageCall;
            document.getElementById('info-el').textContent =
                `${data.total_rows} rows total | Page ${data.page} of ${data.total_pages}`;
            const pag = paginationHtml(data, pageCall);
            document.getElementById('pag-top').innerHTML = pag;
            document.getElementById('pag-bottom').innerHTML = pag;
            document.getElementById('tbody-el').innerHTML = buildRows(data);
        }

        async function silentReload() {
            if (!lastTable || !lastTable.silentFetch) return;
            const gen = viewGen;
            const y = window.scrollY;
            try {
                const data = await lastTable.silentFetch();
                if (!isCurrentView(gen) || !lastTable) return;
                updateTableInPlace(data, lastTable.pageCall);
            } finally {
                window.scrollTo(0, y);
            }
        }

        let tsMode = 'human';
        let lastTable = null;
        let tsLocale = localStorage.getItem('tsLocale') || 'local';

        let viewGen = 0;

        function beginView() {
            return ++viewGen;
        }

        function isCurrentView(gen) {
            return gen === viewGen;
        }

        let liveOn = false;
        let ws = null;
        let currentViewSpec = null;

        function refresh() {
            if (usageViewActive) {
                debug('refresh button pressed');
                usageReload();
            } else {
                debug('refresh button pressed');
                silentReload();
            }
        }

        function toggleLive() {
            liveOn = !liveOn;
            document.getElementById('live-toggle').textContent = liveOn ? 'Live: On' : 'Live: Off';
            document.getElementById('live-toggle').classList.toggle('live-on', liveOn);
            debug(`live button pressed -> ${liveOn ? 'on' : 'off'}`);
            if (liveOn) {
                connectWs();
            } else {
                if (ws) { ws.close(); ws = null; }
            }
        }

        function connectWs() {
            const proto = location.protocol === 'https:' ? 'wss://' : 'ws://';
            ws = new WebSocket(proto + location.host + basePath + '/ws');
            ws.onopen = () => {
                if (currentViewSpec) ws.send(JSON.stringify({ type: 'watch', view: currentViewSpec }));
            };
            ws.onmessage = e => {
                try {
                    const msg = JSON.parse(e.data);
                    if (msg.type === 'reload') {
                        if (usageViewActive) usageReload();
                        else silentReload();
                    }
                } catch (err) {}
            };
            ws.onclose = () => {
                ws = null;
                if (liveOn) setTimeout(connectWs, 2000);
            };
        }

        function setViewSpec(spec) {
            currentViewSpec = spec;
            if (liveOn && ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'watch', view: spec }));
            }
        }

        const localeOptions = [
            { value: 'local', label: 'Local (Browser default)' },
            { value: 'de-DE', label: 'Deutsch (de-DE)' },
            { value: 'en-US', label: 'English (US)' },
            { value: 'en-GB', label: 'English (UK)' },
            { value: 'fr-FR', label: 'Français (fr-FR)' },
            { value: 'es-ES', label: 'Español (es-ES)' },
            { value: 'it-IT', label: 'Italiano (it-IT)' },
            { value: 'nl-NL', label: 'Nederlands (nl-NL)' },
            { value: 'pt-BR', label: 'Português (BR)' },
            { value: 'pl-PL', label: 'Polski (pl-PL)' }
        ];

        let settingsRefreshId = null;

        function stopSettingsRefresh() {
            if (settingsRefreshId) { clearInterval(settingsRefreshId); settingsRefreshId = null; }
        }

        function showSettings() {
            beginView();
            setBack(showHome);
            setViewSpec(null);
            lastTable = null;
            usageViewActive = false;
            stopSettingsRefresh();
            document.getElementById('title').textContent = 'Settings';
            const opts = localeOptions.map(o =>
                `<option value="${o.value}" ${o.value === tsLocale ? 'selected' : ''}>${o.label}</option>`
            ).join('');
            document.getElementById('content').innerHTML =
                '<div class="container"><div class="settings">' +
                '<div class="settings-row">' +
                '<label for="ts-locale">Timestamp format:</label>' +
                `<select id="ts-locale">${opts}</select>` +
                '</div>' +
                `<div class="info">Local uses your browser's language. The other options force a specific language, e.g. Deutsch = "01.08.2026, 12:30:00", US = "8/1/2026, 12:30:00 PM".</div>` +
                '<div class="settings-row">' +
                '<label for="live-interval">Live update interval (seconds):</label>' +
                '<input type="number" id="live-interval" min="1" max="60" value="3">' +
                `<button class="top-btn" onclick="saveLiveInterval()">Save</button>` +
                '</div>' +
                '<div class="info" id="client-info">Loading...</div>' +
                '</div></div>';
            document.getElementById('ts-locale').addEventListener('change', e => {
                tsLocale = e.target.value;
                localStorage.setItem('tsLocale', tsLocale);
                if (lastTable) renderTablePage(lastTable.data, lastTable.pageCall);
            });
            refreshSettingsInfo();
            settingsRefreshId = setInterval(refreshSettingsInfo, 3000);
        }

        async function refreshSettingsInfo() {
            const gen = viewGen;
            try {
                const s = await api('/api/settings');
                if (!isCurrentView(gen)) return;
                document.getElementById('live-interval').value = s.watch_interval;
                document.getElementById('client-info').textContent =
                    `Active clients: ${s.clients} | watched views: ${s.views}`;
            } catch (err) {}
        }

        async function saveLiveInterval() {
            const val = parseInt(document.getElementById('live-interval').value, 10);
            if (!val || val < 1 || val > 60) {
                alert('Interval must be between 1 and 60 seconds');
                return;
            }
            const resp = await fetch(basePath + '/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ watch_interval: val })
            });
            const s = await resp.json();
            if (s.error) {
                alert('Error: ' + s.error);
                return;
            }
            document.getElementById('live-interval').value = s.watch_interval;
            document.getElementById('client-info').textContent =
                `Active clients: ${s.clients} | watched views: ${s.views}`;
            debug(`live interval saved -> ${s.watch_interval}s`);
        }

        function toggleTsMode() {
            tsMode = tsMode === 'human' ? 'raw' : 'human';
            document.getElementById('ts-toggle').textContent =
                tsMode === 'human' ? 'Timestamps: Human' : 'Timestamps: Raw';
            debug(`timestamps button pressed -> ${tsMode === 'human' ? 'human' : 'raw'}`);
            if (lastTable) {
                renderTablePage(lastTable.data, lastTable.pageCall, lastTable.sort, lastTable.sortAction, lastTable.silentFetch);
            }
        }

        function formatTs(val) {
            if (tsMode !== 'human' || val === '') return val;
            const n = Number(val);
            if (!isFinite(n) || n === 0) return val;
            try {
                const locale = tsLocale === 'local' ? undefined : tsLocale;
                return new Date(n * 1000).toLocaleString(locale, {
                    year: 'numeric', month: '2-digit', day: '2-digit',
                    hour: '2-digit', minute: '2-digit', second: '2-digit'
                });
            } catch (e) {
                return val;
            }
        }

        function tableQuery(page, sortKey, sortDir) {
            const qs = new URLSearchParams({ page, page_size: 100 });
            if (sortKey && sortDir) { qs.set('sort', sortKey); qs.set('dir', sortDir); }
            return qs;
        }

        async function showTable(name, page, sortKey, sortDir) {
            const gen = beginView();
            setBack(showTables);
            usageViewActive = false;
            stopSettingsRefresh();
            setViewSpec({ kind: 'table', table: name, page, page_size: 100, sort: sortKey || null, dir: sortDir || null });
            document.getElementById('title').textContent = name;
            showLoading();
            const fetchFn = () => api(`/api/table/${encodeURIComponent(name)}?${tableQuery(page, sortKey, sortDir)}`);
            const data = await fetchFn();
            if (!isCurrentView(gen)) return;
            renderTablePage(
                data,
                p => `showTable('${name}', ${p}, '${sortKey || ''}', '${sortDir || ''}')`,
                sortKey && sortDir ? { key: sortKey, dir: sortDir } : null,
                (k, d) => `showTable('${name}', 1, '${k}', '${d}')`,
                fetchFn
            );
        }

        async function showEntityStates(entity_id, page, sortKey, sortDir) {
            const gen = beginView();
            setBack(() => showUsageView('States', statesConfig));
            usageViewActive = false;
            stopSettingsRefresh();
            setViewSpec({ kind: 'entity', table: 'states', id: entity_id, page, page_size: 100, sort: sortKey || null, dir: sortDir || null });
            document.getElementById('title').textContent = entity_id;
            showLoading();
            const fetchFn = () => api(`/api/entity/${encodeURIComponent(entity_id)}/states?${tableQuery(page, sortKey, sortDir)}`);
            const data = await fetchFn();
            if (!isCurrentView(gen)) return;
            renderTablePage(
                data,
                p => `showEntityStates('${entity_id}', ${p}, '${sortKey || ''}', '${sortDir || ''}')`,
                sortKey && sortDir ? { key: sortKey, dir: sortDir } : null,
                (k, d) => `showEntityStates('${entity_id}', 1, '${k}', '${d}')`,
                fetchFn
            );
        }

        async function showStatisticData(statistic_id, page, sortKey, sortDir, shortTerm) {
            const table = shortTerm ? 'statistics_short_term' : 'statistics';
            const config = shortTerm ? statisticsShortTermConfig : statisticsConfig;
            const gen = beginView();
            setBack(() => showUsageView(shortTerm ? 'Statistics Short Term' : 'Statistics', config));
            usageViewActive = false;
            stopSettingsRefresh();
            setViewSpec({ kind: 'statistic', table, id: statistic_id, page, page_size: 100, sort: sortKey || null, dir: sortDir || null });
            document.getElementById('title').textContent = statistic_id;
            showLoading();
            const fetchFn = () => api(`/api/statistic/${encodeURIComponent(statistic_id)}/data?${tableQuery(page, sortKey, sortDir)}${shortTerm ? '&short_term=1' : ''}`);
            const data = await fetchFn();
            if (!isCurrentView(gen)) return;
            renderTablePage(
                data,
                p => `showStatisticData('${statistic_id}', ${p}, '${sortKey || ''}', '${sortDir || ''}', ${shortTerm ? 'true' : 'false'})`,
                sortKey && sortDir ? { key: sortKey, dir: sortDir } : null,
                (k, d) => `showStatisticData('${statistic_id}', 1, '${k}', '${d}', ${shortTerm ? 'true' : 'false'})`,
                fetchFn
            );
        }

        async function showEventTypeData(event_type, page, sortKey, sortDir) {
            const gen = beginView();
            setBack(() => showUsageView('Events', eventsConfig));
            usageViewActive = false;
            stopSettingsRefresh();
            setViewSpec({ kind: 'event', table: 'events', id: event_type, page, page_size: 100, sort: sortKey || null, dir: sortDir || null });
            document.getElementById('title').textContent = event_type;
            showLoading();
            const fetchFn = () => api(`/api/event-type/${encodeURIComponent(event_type)}/data?${tableQuery(page, sortKey, sortDir)}`);
            const data = await fetchFn();
            if (!isCurrentView(gen)) return;
            renderTablePage(
                data,
                p => `showEventTypeData('${event_type}', ${p}, '${sortKey || ''}', '${sortDir || ''}')`,
                sortKey && sortDir ? { key: sortKey, dir: sortDir } : null,
                (k, d) => `showEventTypeData('${event_type}', 1, '${k}', '${d}')`,
                fetchFn
            );
        }

        showHome();
