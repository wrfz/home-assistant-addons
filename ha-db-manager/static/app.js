        import { html, render, nothing } from './vendor/lit-html/lit-html.js';
        import { repeat } from './vendor/lit-html/directives/repeat.js';

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

        function setContentHtml(html) {
            const el = document.getElementById('content');
            delete el._$litPart$;
            el.innerHTML = html;
        }

        function showLoading() {
            setContentHtml('<div class="loading"><div class="spinner"></div>Loading...</div>');
        }

        function showTitleProgress(on) {
            document.getElementById('title-progress').classList.toggle('hidden', !on);
        }

        function setCleanNewVisible(visible) {
            document.getElementById('clean-new').style.display = visible ? '' : 'none';
        }

        async function cleanNew() {
            const resp = await fetch(basePath + '/api/clean-new', { method: 'POST' });
            const body = await resp.json();
            debug(`clean new pressed -> baselines ${JSON.stringify(body.baselines)}`);
            silentReload();
        }

        async function hideColumn(table, key) {
            const resp = await fetch(basePath + '/api/columns/hide', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ table, column: key })
            });
            const body = await resp.json();
            if (body.error) {
                alert('Error: ' + body.error);
                return;
            }
            debug(`hidden column ${table}.${key}`);
            if (lastTable && lastTable.data && lastTable.data.table_name === table) {
                lastTable.data.columns = lastTable.data.columns.filter(c => c !== key);
                updateTableInPlace(lastTable.data, lastTable.pageCall);
            }
        }

        let columnInfoEl = null;

        function removeColumnInfo() {
            if (columnInfoEl) {
                columnInfoEl.remove();
                columnInfoEl = null;
            }
        }

        function showColumnInfo(event, table, key) {
            event.preventDefault();
            event.stopPropagation();
            removeColumnInfo();
            const meta = tableMeta(table);
            const desc = (meta.column_info || {})[key];
            if (!desc) return;
            const popup = document.createElement('div');
            popup.className = 'col-info-popup';
            popup.innerHTML = '<div class="col-info-popup-title">' + escapeHtml(key) + '</div>' +
                '<div class="col-info-popup-body">' + escapeHtml(desc) + '</div>';
            document.body.appendChild(popup);
            columnInfoEl = popup;
            const rect = event.currentTarget.getBoundingClientRect();
            const pr = popup.getBoundingClientRect();
            let left = rect.left;
            if (left + pr.width > window.innerWidth - 8) {
                left = Math.max(8, window.innerWidth - pr.width - 8);
            }
            let top = rect.bottom + 6;
            if (top + pr.height > window.innerHeight - 8) {
                top = Math.max(8, rect.top - pr.height - 6);
            }
            popup.style.left = left + 'px';
            popup.style.top = top + 'px';
            popup.addEventListener('mouseleave', removeColumnInfo);
        }

        async function showHome() {
            const gen = beginView();
            setBack(null);
            setViewSpec(null);
            tableState = null;
            lastTable = null;
            stopSettingsRefresh();
            setCleanNewVisible(false);
            document.getElementById('title').textContent = 'Home Assistant DB Manager';
            showLoading();

            const tables = await loadTablesMeta();
            if (!isCurrentView(gen)) return;

            const meta = tables.filter(t => t.counts);
            const rest = tables.filter(t => !t.counts);

            let html = '<div class="menu-section"><h2>Tables</h2><div class="button-grid">';
            for (const t of meta) {
                html += `<button class="nav-button" onclick="showTable('${t.name}', 1, '', '', null)">${t.label || t.name}</button>`;
            }
            html += '</div></div>';

            if (rest.length) {
                html += '<div class="table-gap"></div>';
                html += '<div class="menu-section"><div class="button-grid">';
                for (const t of rest) {
                    html += `<button class="nav-button" onclick="showTable('${t.name}', 1, '', '', null)">${t.name}</button>`;
                }
                html += '</div></div>';
            }

            html += '<div class="menu-section"><h2>Settings</h2><div class="button-grid">';
            html += `<button class="nav-button" onclick="showSettings()">Settings</button>`;
            html += '</div></div>';

            setContentHtml(html);
        }

        let tablesMeta = null;
        let tableState = null;
        let tableFilter = null;
        let backTo = null;

        async function loadTablesMeta() {
            if (tablesMeta) return tablesMeta;
            tablesMeta = await api('/api/tables');
            return tablesMeta;
        }

        function tableMeta(name) {
            return (tablesMeta || []).find(t => t.name === name) || {};
        }

        function tableQuery(name, counts, page, sortKey, sortDir) {
            const qs = new URLSearchParams({ page, page_size: 100 });
            if (counts) qs.set('counts', '1');
            if (sortKey && sortDir) { qs.set('sort', sortKey); qs.set('dir', sortDir); }
            if (tableFilter) {
                qs.set('filter_col', tableFilter.col);
                qs.set('filter_value', tableFilter.value);
            }
            return qs;
        }

        function normalizeFilter(filter) {
            if (filter && typeof filter === 'object') return filter;
            if (typeof filter === 'string' && filter.includes('=')) {
                const i = filter.indexOf('=');
                return { col: filter.slice(0, i), value: filter.slice(i + 1) };
            }
            return null;
        }

        function tableColumns(meta, data) {
            const links = meta.links || {};
            const virtual = meta.virtual_cols || [];
            return data.columns.map(key => {
                const link = links[key];
                const cls = virtual.includes(key) ? 'virtual' : '';
                if (link) {
                    return {
                        key,
                        label: key === 'new_count' ? 'new' : key,
                        cls,
                        click: row => showLinked(link.target, link.filter_col, String(row[link.value_col] ?? ''))
                    };
                }
                return { key, label: key === 'new_count' ? 'new' : key, cls };
            });
        }

        async function showTable(name, page, sortKey, sortDir, filter) {
            const gen = beginView();
            stopSettingsRefresh();
            const bt = backTo;
            setBack(bt
                ? () => showTable(bt.name, bt.page, bt.sortKey, bt.sortDir, bt.filter)
                : showHome);

            const f = normalizeFilter(filter);
            tableFilter = f;
            backTo = null;

            const meta = tableMeta(name);
            const counts = !!meta.counts;
            setCleanNewVisible(counts);
            const sk = sortKey || (counts ? (meta.default_sort || null) : null);
            const sd = sortDir || (counts ? 'asc' : null);
            tableState = { name, page, sortKey: sk, sortDir: sd, filter: tableFilter };

            const titleEl = document.getElementById('title');
            titleEl.textContent = meta.label || name;
            showLoading();
            const fetchFn = () => api(`/api/table/${encodeURIComponent(name)}?${tableQuery(name, counts, page, sk, sd)}`);
            const data = await fetchFn();
            if (!isCurrentView(gen)) return;

            if (tableFilter && data.filter_label) {
                titleEl.textContent = `${meta.label || name} of \`${data.filter_label}\``;
            }

            const spec = { kind: 'table', table: name, counts, page, page_size: 100, sort: sk, dir: sd };
            if (tableFilter) {
                spec.filter_col = tableFilter.col;
                spec.filter_value = tableFilter.value;
            }
            setViewSpec(spec);

            renderTablePage(
                data,
                p => reloadTable(name, p, sk || '', sd || '', tableFilter),
                sk && sd ? { key: sk, dir: sd } : null,
                (k, d) => reloadTable(name, 1, k, d, tableFilter),
                fetchFn,
                d => tableColumns(meta, d)
            );
        }

        async function reloadTable(name, page, sortKey, sortDir, filter) {
            if (!lastTable) {
                showTable(name, page, sortKey, sortDir, filter);
                return;
            }
            const gen = beginView();
            const f = normalizeFilter(filter);
            const meta = tableMeta(name);
            const counts = !!meta.counts;
            setCleanNewVisible(counts);
            const sk = sortKey || (counts ? (meta.default_sort || null) : null);
            const sd = sortDir || (counts ? 'asc' : null);
            tableState = { name, page, sortKey: sk, sortDir: sd, filter: f || tableFilter };

            showTitleProgress(true);
            try {
                const fetchFn = () => api(`/api/table/${encodeURIComponent(name)}?${tableQuery(name, counts, page, sk, sd)}`);
                const data = await fetchFn();
                if (!isCurrentView(gen) || !lastTable) return;

                const spec = { kind: 'table', table: name, counts, page, page_size: 100, sort: sk, dir: sd };
                if (tableFilter) {
                    spec.filter_col = tableFilter.col;
                    spec.filter_value = tableFilter.value;
                }
                setViewSpec(spec);

                lastTable.sort = sk && sd ? { key: sk, dir: sd } : null;
                lastTable.sortAction = (k, d) => reloadTable(name, 1, k, d, tableFilter);
                lastTable.silentFetch = fetchFn;
                updateTableInPlace(data, p => reloadTable(name, p, sk || '', sd || '', tableFilter));
            } finally {
                showTitleProgress(false);
            }
        }

        function showLinked(target, filterCol, filterValue) {
            backTo = tableState ? { name: tableState.name, page: tableState.page, sortKey: tableState.sortKey, sortDir: tableState.sortDir, filter: tableState.filter } : null;
            showTable(target, 1, '', '', { col: filterCol, value: filterValue });
        }

        function paginationTemplate(data, pageCall) {
            return html`
                <button @click=${() => pageCall(data.page - 1)} ?disabled=${data.page <= 1}>&laquo; Prev</button>
                <span>${data.page}</span>
                <button @click=${() => pageCall(data.page + 1)} ?disabled=${data.page >= data.total_pages}>Next &raquo;</button>`;
        }

        function buildRows(data, cols) {
            const list = cols || data.columns;
            return repeat(data.rows, (row, i) => i, row => {
                const cells = list.map(c => {
                    const key = typeof c === 'object' ? c.key : c;
                    const cls = typeof c === 'object' && c.cls ? c.cls : nothing;
                    const val = row[key];
                    const isNull = val === null || val === undefined;
                    const raw = isNull ? '' : val;
                    const display = isNull
                        ? html`<span class="null-cell">NULL</span>`
                        : (key.endsWith('_ts') ? formatTs(raw) : raw);
                    if (typeof c === 'object' && c.click && raw != null && raw !== '') {
                        return html`<td class=${cls}><a @click=${() => c.click(row)}>${display}</a></td>`;
                    }
                    return html`<td class=${cls} title=${isNull ? '' : String(raw)}>${display}</td>`;
                });
                return html`<tr>${cells}</tr>`;
            });
        }

        function buildThead(data, sort, sortAction, cols) {
            const list = cols || data.columns;
            const tableName = data.table_name;
            const meta = tableMeta(tableName);
            const protectedCols = (meta.links
                ? Object.keys(meta.links).concat(Object.values(meta.links).map(l => l.value_col))
                : [])
                .concat(meta.virtual_cols || []);
            return html`<tr>${list.map(c => {
                const key = typeof c === 'object' ? c.key : c;
                const label = typeof c === 'object' ? c.label : c;
                const cls = typeof c === 'object' && c.cls ? c.cls : nothing;
                const isSorted = sort && sort.key === key;
                const arrow = isSorted ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : '';
                const sortable = !(typeof c === 'object' && c.sortable === false);
                const sortClick = sortAction && sortable
                    ? () => sortAction(key, isSorted && sort.dir === 'asc' ? 'desc' : 'asc')
                    : undefined;
                const info = html`<span class="col-info" title="Column info" @click=${e => showColumnInfo(e, tableName, key)}>i</span>`;
                const hide = protectedCols.includes(key) ? nothing :
                    html`<span class="col-hide" title="Hide this column" @click=${e => { e.stopPropagation(); hideColumn(tableName, key); }}>&times;</span>`;
                const actions = html`<span class="col-actions">${info}${hide}</span>`;
                return html`<th class="sortable ${cls}" style="cursor:pointer" @click=${sortClick}><span class="th-inner"><span class="col-label">${label}${arrow}</span>${actions}</span></th>`;
            })}</tr>`;
        }

        function renderTableView(data, pageCall, sort, sortAction, silentFetch, colsFn) {
            const cols = colsFn ? colsFn(data) : null;
            const el = document.getElementById('content');
            if (!el._$litPart$) el.innerHTML = '';
            render(html`
                <div class="info" id="info-el">${data.total_rows} rows total | Page ${data.page} of ${data.total_pages}</div>
                <div class="pagination" id="pag-top">${paginationTemplate(data, pageCall)}</div>
                <div class="container"><table>
                    <thead id="thead-el">${buildThead(data, sort, sortAction, cols)}</thead>
                    <tbody id="tbody-el">${buildRows(data, cols)}</tbody>
                </table></div>
                <div class="pagination" id="pag-bottom">${paginationTemplate(data, pageCall)}</div>`,
                el);
        }

        function renderTablePage(data, pageCall, sort, sortAction, silentFetch, colsFn) {
            lastTable = { data, pageCall, sort, sortAction, silentFetch, colsFn };
            renderTableView(data, pageCall, sort, sortAction, silentFetch, colsFn);
        }

        function updateTableInPlace(data, pageCall) {
            if (!lastTable) return;
            removeColumnInfo();
            lastTable.data = data;
            lastTable.pageCall = pageCall;
            renderTableView(data, lastTable.pageCall, lastTable.sort, lastTable.sortAction, lastTable.silentFetch, lastTable.colsFn);
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
            removeColumnInfo();
            return ++viewGen;
        }

        function isCurrentView(gen) {
            return gen === viewGen;
        }

        let liveOn = true;
        let ws = null;
        let currentViewSpec = null;

        function refresh() {
            debug('refresh button pressed');
            silentReload();
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

        if (liveOn) {
            document.getElementById('live-toggle').textContent = 'Live: On';
            document.getElementById('live-toggle').classList.add('live-on');
            connectWs();
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
                        silentReload();
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
            stopSettingsRefresh();
            setCleanNewVisible(false);
            document.getElementById('title').textContent = 'Settings';
            const opts = localeOptions.map(o =>
                `<option value="${o.value}" ${o.value === tsLocale ? 'selected' : ''}>${o.label}</option>`
            ).join('');
            setContentHtml(
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
                '<div class="settings-row">' +
                '<button class="top-btn" id="hide-empty-btn" onclick="hideEmptyColumns()">Hide Empty Columns</button>' +
                '<button class="top-btn" id="show-all-btn" onclick="showAllColumns()">Show All Columns</button>' +
                '<span id="column-progress" class="title-progress hidden"></span>' +
                '</div>' +
                '<div class="info" id="hidden-cols-info">Hidden columns: none</div>' +
                '<div class="info" id="client-info">Loading...</div>' +
                '</div></div>');
            document.getElementById('ts-locale').addEventListener('change', e => {
                tsLocale = e.target.value;
                localStorage.setItem('tsLocale', tsLocale);
                if (lastTable) renderTablePage(lastTable.data, lastTable.pageCall, lastTable.sort, lastTable.sortAction, lastTable.silentFetch, lastTable.colsFn);
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
                renderHiddenColumns(s.hidden_columns);
            } catch (err) {}
        }

        function escapeHtml(value) {
            return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }

        function renderHiddenColumns(hidden) {
            const el = document.getElementById('hidden-cols-info');
            if (!el) return;
            const entries = Object.entries(hidden || {}).filter(([, cols]) => cols.length);
            if (!entries.length) {
                el.innerHTML = 'Hidden columns: none';
                return;
            }
            el.innerHTML = 'Hidden columns:' +
                entries.map(([table, cols]) =>
                    '<div class="hidden-table">' + escapeHtml(table) +
                    cols.map(col => '<div class="hidden-col">' + escapeHtml(col) + '</div>').join('') +
                    '</div>'
                ).join('');
        }

        function setColumnsBusy(busy) {
            const hideBtn = document.getElementById('hide-empty-btn');
            const showBtn = document.getElementById('show-all-btn');
            const progress = document.getElementById('column-progress');
            if (!hideBtn || !showBtn || !progress) return;
            hideBtn.disabled = busy;
            showBtn.disabled = busy;
            progress.classList.toggle('hidden', !busy);
        }

        async function hideEmptyColumns() {
            setColumnsBusy(true);
            try {
                const resp = await fetch(basePath + '/api/columns/hide-empty', { method: 'POST' });
                const body = await resp.json();
                if (body.error) {
                    alert('Error: ' + body.error);
                    return;
                }
                debug('hide empty columns -> ' + JSON.stringify(body.hidden_columns));
                renderHiddenColumns(body.hidden_columns);
            } finally {
                setColumnsBusy(false);
            }
        }

        async function showAllColumns() {
            setColumnsBusy(true);
            try {
                const resp = await fetch(basePath + '/api/columns/show-all', { method: 'POST' });
                const body = await resp.json();
                if (body.error) {
                    alert('Error: ' + body.error);
                    return;
                }
                debug('show all columns -> ' + JSON.stringify(body.hidden_columns));
                renderHiddenColumns(body.hidden_columns);
            } finally {
                setColumnsBusy(false);
            }
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
                renderTablePage(lastTable.data, lastTable.pageCall, lastTable.sort, lastTable.sortAction, lastTable.silentFetch, lastTable.colsFn);
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

        // The remaining views (menu, settings) and the top buttons in index.html
        // still use inline onclick attributes, which cannot see module scope.
        Object.assign(window, {
            toggleLive, refresh, cleanNew, toggleTsMode, goBack,
            showTable, showSettings, saveLiveInterval, hideEmptyColumns, showAllColumns
        });

        showHome();
