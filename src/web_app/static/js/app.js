/* Main Frontend Application Logic */

document.addEventListener('DOMContentLoaded', () => {
  const yearSlider = document.getElementById('year-slider');
  const yearValue = document.getElementById('year-value');
  const activeAfterSlider = document.getElementById('active-after-slider');
  const activeAfterValue = document.getElementById('active-after-value');

  const minWeightSelect = document.getElementById('min-weight-select');
  const maxCommSelect = document.getElementById('max-comm-select');
  const btnRun = document.getElementById('btn-run-clustering');
  
  const kpiNodes = document.getElementById('kpi-nodes');
  const kpiEdges = document.getElementById('kpi-edges');
  const kpiComms = document.getElementById('kpi-comms');
  const kpiModularity = document.getElementById('kpi-modularity');
  
  const communityGrid = document.getElementById('community-grid');
  const matrixContainer = document.getElementById('matrix-container');
  
  // Modal Elements
  const modalOverlay = document.getElementById('community-modal');
  const modalTitle = document.getElementById('modal-title');
  const btnCloseModal = document.getElementById('btn-close-modal');
  const sidebarContent = document.getElementById('sidebar-content');
  
  let currentClusterData = null;
  const graphViz = new CommunityGraphViz('graph-canvas');

  // Tab Switching Logic
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabPanes = document.querySelectorAll('.tab-pane');

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      tabPanes.forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const targetId = btn.getAttribute('data-target');
      const targetPane = document.getElementById(targetId);
      if (targetPane) targetPane.classList.add('active');

      if (targetId === 'median-view') {
        if (!medianResultsGrid.children.length || medianResultsGrid.innerHTML.trim() === '') {
          fetchMedianActors();
        }
      }
    });
  });

  // Median Actors Logic
  const medianAllDataCheckbox = document.getElementById('median-all-data');
  const medianStartSlider = document.getElementById('median-start-slider');
  const medianStartValue = document.getElementById('median-start-value');
  const medianEndSlider = document.getElementById('median-end-slider');
  const medianEndValue = document.getElementById('median-end-value');
  const btnRunMedian = document.getElementById('btn-run-median');
  const medianLoading = document.getElementById('median-loading');
  const medianResultsGrid = document.getElementById('median-results-grid');

  medianStartSlider.addEventListener('input', (e) => {
    medianStartValue.textContent = e.target.value;
  });

  medianEndSlider.addEventListener('input', (e) => {
    medianEndValue.textContent = e.target.value;
  });

  medianAllDataCheckbox.addEventListener('change', (e) => {
    const isChecked = e.target.checked;
    medianStartSlider.disabled = isChecked;
    medianEndSlider.disabled = isChecked;
  });

  async function fetchMedianActors() {
    const isAllData = medianAllDataCheckbox.checked;
    const startYear = isAllData ? null : parseInt(medianStartSlider.value);
    const endYear = isAllData ? null : parseInt(medianEndSlider.value);

    btnRunMedian.innerHTML = '⚡ Computing...';
    btnRunMedian.disabled = true;
    medianResultsGrid.innerHTML = '';
    medianLoading.style.display = 'block';

    try {
      const res = await fetch('/api/median_actors', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ start_year: startYear, end_year: endYear, top_k: 5 })
      });
      const data = await res.json();
      
      medianLoading.style.display = 'none';
      if (data.error) {
        medianResultsGrid.innerHTML = `<div style="color:var(--accent-rose); padding:20px;">${data.error}</div>`;
        document.getElementById('popular-results-grid').innerHTML = '';
        document.getElementById('kevin-bacon-container').innerHTML = '';
      } else {
        renderMedianResults(data.top_medians);
        renderPopularResults(data.top_popular);
        renderKevinBaconStats(data.kevin_bacon);
      }
    } catch (err) {
      medianLoading.style.display = 'none';
      medianResultsGrid.innerHTML = `<div style="color:var(--accent-rose); padding:20px;">Error: ${err.message}</div>`;
      document.getElementById('popular-results-grid').innerHTML = '';
      document.getElementById('kevin-bacon-container').innerHTML = '';
    } finally {
      btnRunMedian.innerHTML = '<span>⚡ Find Median Actors</span>';
      btnRunMedian.disabled = false;
    }
  }

  btnRunMedian.addEventListener('click', fetchMedianActors);

  function renderPopularResults(popular) {
    const popularGrid = document.getElementById('popular-results-grid');
    if (!popular || popular.length === 0) {
      popularGrid.innerHTML = '<div style="color:var(--text-muted); padding:20px;">No popular actors data available for this selection.</div>';
      return;
    }

    const html = popular.map((m, idx) => {
      // Hop distribution progress bars HTML (using same format)
      const hopBarsHtml = (m.hop_distribution || []).map(h => `
        <div class="genre-row" style="margin-bottom:6px;">
          <div class="genre-info">
            <span>${h.hop} Hop${h.hop > 1 ? 's' : ''} Distance</span>
            <span><strong style="color:var(--accent-cyan);">${h.percentage}%</strong> (${h.count.toLocaleString()} actors)</span>
          </div>
          <div class="genre-bar-bg">
            <div class="genre-bar-fill" style="width: ${Math.min(h.percentage, 100)}%; background: linear-gradient(90deg, #34d399, #38bdf8);"></div>
          </div>
        </div>
      `).join('');

      return `
        <div class="comm-card median-card" style="border-top: 4px solid var(--accent-emerald);">
          <div class="median-rank" style="color: var(--accent-emerald);">#${idx + 1}</div>
          <div class="median-name">${m.name}</div>
          <div style="font-size:11px; color:var(--text-muted); margin-bottom:12px; text-transform:uppercase; letter-spacing:0.5px;">
            ${(m.professions || []).join(' • ') || 'ACTOR'}
          </div>

          <div style="display:flex; flex-wrap:wrap; gap:8px; justify-content:center; margin-bottom:16px;">
            <span class="median-path" style="background:rgba(52, 211, 153, 0.15); color:var(--accent-emerald);">Popularity Score: ${m.popularity_score}</span>
            <span class="median-path" style="background:rgba(251, 191, 36, 0.15); color:var(--accent-amber);">Movies in Window: ${m.movies_in_window}</span>
            <span class="median-path" style="background:rgba(129, 140, 248, 0.15); color:var(--accent-purple);">Direct Co-Stars: ${(m.direct_co_stars || 0).toLocaleString()}</span>
          </div>

          <!-- Normal Distribution & Centrality Parameters Grid -->
          <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border-color); border-radius:10px; padding:12px; margin-bottom:16px; width:100%; text-align:left;">
            <div style="font-size:11px; font-weight:700; color:var(--accent-emerald); text-transform:uppercase; margin-bottom:8px; text-align:center;">
              📊 Network Scale & Distribution
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:12px;">
              <div style="background:rgba(255,255,255,0.03); padding:8px; border-radius:6px;">
                <div style="color:var(--text-muted); font-size:10px;">Mean Distance (μ)</div>
                <div style="color:#fff; font-weight:700;">${m.avg_path || 'N/A'} hops</div>
              </div>
              <div style="background:rgba(255,255,255,0.03); padding:8px; border-radius:6px;">
                <div style="color:var(--text-muted); font-size:10px;">Std Dev (σ)</div>
                <div style="color:#fff; font-weight:700;">±${m.std_dev || 'N/A'}</div>
              </div>
              <div style="background:rgba(255,255,255,0.03); padding:8px; border-radius:6px;">
                <div style="color:var(--text-muted); font-size:10px;">Variance (σ²)</div>
                <div style="color:#fff; font-weight:700;">${m.variance || 'N/A'}</div>
              </div>
              <div style="background:rgba(255,255,255,0.03); padding:8px; border-radius:6px;">
                <div style="color:var(--text-muted); font-size:10px;">Closeness Centrality</div>
                <div style="color:var(--accent-cyan); font-weight:700;">${m.closeness || 'N/A'}</div>
              </div>
            </div>
            <div style="font-size:11px; color:var(--text-dim); text-align:center; margin-top:8px;">
              Total Path Sum: ${(m.total_path_sum || 0).toLocaleString()}
            </div>
          </div>

          <!-- Distance Breakdown Histogram -->
          <div style="width:100%; text-align:left;">
            <div style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; margin-bottom:8px;">
              🌐 Hop Distance Breakdown (Histogram)
            </div>
            ${hopBarsHtml}
          </div>
        </div>
      `;
    }).join('');

    popularGrid.innerHTML = html;
  }

  function renderMedianResults(medians) {
    if (!medians || medians.length === 0) {
      medianResultsGrid.innerHTML = '<div style="color:var(--text-muted); padding:20px;">No actors found for this selection.</div>';
      return;
    }

    const html = medians.map(m => {
      // Hop distribution progress bars HTML
      const hopBarsHtml = (m.hop_distribution || []).map(h => `
        <div class="genre-row" style="margin-bottom:6px;">
          <div class="genre-info">
            <span>${h.hop} Hop${h.hop > 1 ? 's' : ''} Distance</span>
            <span><strong style="color:var(--accent-cyan);">${h.percentage}%</strong> (${h.count.toLocaleString()} actors)</span>
          </div>
          <div class="genre-bar-bg">
            <div class="genre-bar-fill" style="width: ${Math.min(h.percentage, 100)}%; background: linear-gradient(90deg, #34d399, #38bdf8);"></div>
          </div>
        </div>
      `).join('');

      return `
        <div class="comm-card median-card">
          <div class="median-rank">#${m.rank}</div>
          <div class="median-name">${m.name}</div>
          <div style="font-size:11px; color:var(--text-muted); margin-bottom:12px; text-transform:uppercase; letter-spacing:0.5px;">
            ${(m.professions || []).join(' • ') || 'ACTOR'}
          </div>

          <div style="display:flex; flex-wrap:wrap; gap:8px; justify-content:center; margin-bottom:16px;">
            <span class="median-path">Avg Path (μ): ${m.avg_path} hops</span>
            <span class="median-path" style="background:rgba(244, 63, 94, 0.15); color:var(--accent-rose);">Longest Path (Max): ${m.max_path} hops</span>
            <span class="median-path" style="background:rgba(129, 140, 248, 0.15); color:var(--accent-purple);">Direct Co-Stars: ${m.direct_co_stars.toLocaleString()}</span>
          </div>

          <!-- Normal Distribution & Centrality Parameters Grid -->
          <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border-color); border-radius:10px; padding:12px; margin-bottom:16px; width:100%; text-align:left;">
            <div style="font-size:11px; font-weight:700; color:var(--accent-amber); text-transform:uppercase; margin-bottom:8px; text-align:center;">
              📊 Normal Distribution & Centrality Parameters
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:12px;">
              <div style="background:rgba(255,255,255,0.03); padding:8px; border-radius:6px;">
                <div style="color:var(--text-muted); font-size:10px;">Mean Distance (μ)</div>
                <div style="color:#fff; font-weight:700;">${m.avg_path} hops</div>
              </div>
              <div style="background:rgba(255,255,255,0.03); padding:8px; border-radius:6px;">
                <div style="color:var(--text-muted); font-size:10px;">Std Dev (σ)</div>
                <div style="color:#fff; font-weight:700;">±${m.std_dev}</div>
              </div>
              <div style="background:rgba(255,255,255,0.03); padding:8px; border-radius:6px;">
                <div style="color:var(--text-muted); font-size:10px;">Variance (σ²)</div>
                <div style="color:#fff; font-weight:700;">${m.variance}</div>
              </div>
              <div style="background:rgba(255,255,255,0.03); padding:8px; border-radius:6px;">
                <div style="color:var(--text-muted); font-size:10px;">Closeness Centrality</div>
                <div style="color:var(--accent-cyan); font-weight:700;">${m.closeness}</div>
              </div>
            </div>
            <div style="font-size:11px; color:var(--text-dim); text-align:center; margin-top:8px;">
              Total Path Sum: ${m.total_path_sum.toLocaleString()}
            </div>
          </div>

          <!-- Distance Breakdown Histogram -->
          <div style="width:100%; text-align:left;">
            <div style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; margin-bottom:8px;">
              🌐 Hop Distance Breakdown (Histogram)
            </div>
            ${hopBarsHtml}
          </div>
        </div>
      `;
    }).join('');

    medianResultsGrid.innerHTML = html;
  }

  function renderKevinBaconStats(kb) {
    const kbGrid = document.getElementById('kevin-bacon-container');
    if (!kb) {
      kbGrid.innerHTML = '<div style="color:var(--text-muted); padding:20px;">Kevin Bacon is not connected in this sub-graph window.</div>';
      return;
    }

    const hopBarsHtml = (kb.hop_distribution || []).map(h => `
      <div class="genre-row" style="margin-bottom:6px;">
        <div class="genre-info">
          <span>${h.hop} Hop${h.hop > 1 ? 's' : ''} Distance</span>
          <span><strong style="color:var(--accent-orange);">${h.percentage}%</strong> (${h.count.toLocaleString()} actors)</span>
        </div>
        <div class="genre-bar-bg">
          <div class="genre-bar-fill" style="width: ${Math.min(h.percentage, 100)}%; background: linear-gradient(90deg, #fb923c, #f97316);"></div>
        </div>
      </div>
    `).join('');

    kbGrid.innerHTML = `
      <div class="comm-card median-card" style="border-top: 4px solid var(--accent-orange); background: rgba(251, 146, 60, 0.05);">
        <div class="median-rank" style="color: var(--accent-orange);">★</div>
        <div class="median-name">${kb.name}</div>
        <div style="font-size:11px; color:var(--text-muted); margin-bottom:12px; text-transform:uppercase; letter-spacing:0.5px;">
          ${(kb.professions || []).join(' • ') || 'ACTOR'}
        </div>

        <div style="margin-bottom:16px;">
          <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
            <span style="font-size:12px; color:var(--text-muted);">Direct Co-Stars (1-Hop):</span>
            <strong style="color:#fff;">${(kb.direct_co_stars || 0).toLocaleString()}</strong>
          </div>
          <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
            <span style="font-size:12px; color:var(--text-muted);">Average Degrees (μ):</span>
            <strong style="color:var(--accent-orange); font-size:14px;">${kb.avg_path || 'N/A'}</strong>
          </div>
          <div style="display:flex; justify-content:space-between;">
            <span style="font-size:12px; color:var(--text-muted);">Network Reach (Max Hop):</span>
            <strong style="color:#fff;">${kb.max_path || 'N/A'}</strong>
          </div>
        </div>

        <!-- Metrics Grid -->
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; margin-bottom:16px; text-align:center;">
          <div style="background:rgba(255,255,255,0.03); padding:8px; border-radius:6px;">
            <div style="color:var(--text-muted); font-size:10px;">Std Dev (σ)</div>
            <div style="color:#fff; font-weight:700;">±${kb.std_dev || 'N/A'}</div>
          </div>
          <div style="background:rgba(255,255,255,0.03); padding:8px; border-radius:6px;">
            <div style="color:var(--text-muted); font-size:10px;">Variance (σ²)</div>
            <div style="color:#fff; font-weight:700;">${kb.variance || 'N/A'}</div>
          </div>
          <div style="background:rgba(255,255,255,0.03); padding:8px; border-radius:6px;">
            <div style="color:var(--text-muted); font-size:10px;">Closeness Centrality</div>
            <div style="color:var(--accent-orange); font-weight:700;">${kb.closeness || 'N/A'}</div>
          </div>
        </div>
        <div style="font-size:11px; color:var(--text-dim); text-align:center; margin-top:8px;">
          Total Path Sum: ${(kb.total_path_sum || 0).toLocaleString()}
        </div>

        <!-- Distance Breakdown Histogram -->
        <div style="width:100%; text-align:left; margin-top:16px;">
          <div style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; margin-bottom:8px;">
            🌐 Hop Distance Breakdown (Histogram)
          </div>
          ${hopBarsHtml}
        </div>
      </div>
    `;
  }
  // Sync Slider Value Displays
  yearSlider.addEventListener('input', (e) => {
    yearValue.textContent = e.target.value;
  });

  activeAfterSlider.addEventListener('input', (e) => {
    const val = parseInt(e.target.value);
    activeAfterValue.textContent = val <= 1800 ? 'All Time (1800)' : val;
  });

  // Run Clustering Button Action
  btnRun.addEventListener('click', () => {
    runClustering();
  });

  // Initial Load
  fetchYears();
  runClustering();

  async function fetchYears() {
    try {
      const res = await fetch('/api/years');
      const data = await res.json();
      yearSlider.min = data.min_year;
      yearSlider.max = data.max_year;
      yearSlider.value = data.default_created_before || 2010;
      yearValue.textContent = yearSlider.value;

      activeAfterSlider.min = 1800;
      activeAfterSlider.max = data.max_year;
      activeAfterSlider.value = data.default_active_after || 1800;
      activeAfterValue.textContent = activeAfterSlider.value <= 1800 ? 'All Time (1800)' : activeAfterSlider.value;
    } catch (err) {
      console.error('Failed to fetch years:', err);
    }
  }

  async function runClustering() {
    const createdBefore = parseInt(yearSlider.value);
    const activeAfter = parseInt(activeAfterSlider.value);
    const minWeight = parseInt(minWeightSelect.value);
    const maxCommunities = parseInt(maxCommSelect.value);

    btnRun.innerHTML = '⚡ Computing Graph...';
    btnRun.disabled = true;

    try {
      const res = await fetch('/api/cluster', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          created_before: createdBefore,
          active_after: activeAfter,
          min_weight: minWeight,
          max_communities: maxCommunities
        })
      });

      const data = await res.json();
      currentClusterData = data;
      renderDashboard(data);
    } catch (err) {
      console.error('Clustering error:', err);
      alert('Error running community clustering: ' + err.message);
    } finally {
      btnRun.innerHTML = '<span>⚡ Run Clustering</span>';
      btnRun.disabled = false;
    }
  }

  function renderDashboard(data) {
    // Update KPI Cards
    kpiNodes.textContent = (data.total_nodes || 0).toLocaleString();
    kpiEdges.textContent = (data.total_edges || 0).toLocaleString();
    kpiComms.textContent = (data.total_communities_found || 0).toLocaleString();
    kpiModularity.textContent = data.modularity_score !== undefined ? data.modularity_score : 'N/A';

    // Render Community Grid
    renderCommunityGrid(data.communities || []);

    // Render Inter-Community Adjacency Matrix
    renderInterCommunityMatrix(data.inter_community_matrix || []);
  }

  function renderCommunityGrid(communities) {
    communityGrid.innerHTML = '';
    if (!communities || communities.length === 0) {
      communityGrid.innerHTML = '<div style="color:var(--text-muted); padding:20px;">No communities detected for this selection.</div>';
      return;
    }

    communities.forEach(c => {
      const card = document.createElement('div');
      card.className = 'comm-card';

      // Geographical Tag Badge HTML
      const geoTag = c.geo_tag || { region: 'Global Cinema', flag: '🌐', primary_hub: 'International', geo_summary: '' };
      const geoHtml = `
        <div class="geo-tag-bar">
          <span class="geo-tag-badge">${geoTag.flag} ${geoTag.region}</span>
          <span class="geo-hub-chip">📍 ${geoTag.primary_hub}</span>
        </div>
      `;

      // Tag Pills HTML
      const tagsHtml = (c.profession_tags || []).slice(0, 4).map(t => 
        `<span class="tag-pill">${t.tag}<span class="pct">${t.percentage}%</span></span>`
      ).join('');

      // Genre Progress Bars HTML
      const genresHtml = (c.top_genres || []).slice(0, 3).map(g => `
        <div class="genre-row">
          <div class="genre-info">
            <span>${g.genre}</span>
            <span>${g.percentage}%</span>
          </div>
          <div class="genre-bar-bg">
            <div class="genre-bar-fill" style="width: ${g.percentage}%"></div>
          </div>
        </div>
      `).join('');

      // Top Actors Chips
      const actorsHtml = (c.top_actors || []).slice(0, 4).map(a => 
        `<span class="actor-chip">🌟 ${a.name}</span>`
      ).join('');

      card.innerHTML = `
        <div>
          <div class="comm-header">
            <span class="comm-badge">Community #${c.id}</span>
            <span style="font-size:12px; color:var(--text-muted);">Density: ${c.internal_density}</span>
          </div>
          <div class="comm-archetype">${c.archetype}</div>
          
          ${geoHtml}

          <div class="comm-stats-row">
            <span>👥 ${c.node_count} Actors</span>
            <span>🔗 ${c.internal_edges} Intra-Edges</span>
          </div>

          <div style="font-size:12px; font-weight:600; color:var(--text-muted); margin-bottom:6px;">Top Professions / Tags:</div>
          <div class="tag-list">${tagsHtml}</div>

          <div style="font-size:12px; font-weight:600; color:var(--text-muted); margin-bottom:6px;">Genre Profile:</div>
          <div class="genre-bars">${genresHtml}</div>

          <div style="font-size:12px; font-weight:600; color:var(--text-muted); margin-bottom:6px;">Key Stars:</div>
          <div class="actor-roster">${actorsHtml}</div>
        </div>

        <button class="btn-inspect" data-comm-id="${c.id}">
          🔍 Open Community & View Graph
        </button>
      `;

      card.querySelector('.btn-inspect').addEventListener('click', () => {
        openCommunityModal(c.id);
      });

      communityGrid.appendChild(card);
    });
  }

  function renderInterCommunityMatrix(matrix) {
    if (!matrix || matrix.length === 0) {
      matrixContainer.innerHTML = '';
      return;
    }

    let html = `
      <div style="font-size:16px; font-weight:700; margin-bottom:12px;">Inter-Community Connection Matrix</div>
      <table class="matrix-table">
        <thead>
          <tr>
            <th>Community</th>
            ${matrix.map(m => `<th>#${m.source}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
    `;

    matrix.forEach(row => {
      html += `<tr><th>#${row.source}</th>`;
      row.targets.forEach(t => {
        const isSelf = row.source === t.target;
        const opacity = Math.min(t.count / 20, 1);
        const bg = isSelf 
          ? `rgba(99, 102, 241, ${0.15 + opacity * 0.5})` 
          : `rgba(56, 189, 248, ${opacity * 0.4})`;
        
        html += `<td class="matrix-cell" style="background:${bg}; color:#ffffff">${t.count}</td>`;
      });
      html += '</tr>';
    });

    html += '</tbody></table>';
    matrixContainer.innerHTML = html;
  }

  let activeCommunitySummary = null;
  let activeCommunityNodes = [];

  // Connect graph node click listener to actor stats inspector
  graphViz.setNodeClickListener((nodeData) => {
    fetchAndRenderActorStats(nodeData.id);
  });

  // Open Community Modal & Fetch Graph
  async function openCommunityModal(commId) {
    const createdBefore = parseInt(yearSlider.value);
    const activeAfter = parseInt(activeAfterSlider.value);
    const minWeight = parseInt(minWeightSelect.value);

    modalTitle.textContent = `Community #${commId} Inspection & Bridges`;
    modalOverlay.classList.add('active');

    sidebarContent.innerHTML = '<div style="color:var(--text-muted); padding:20px;">Loading community subgraph...</div>';

    try {
      const res = await fetch(`/api/community/${createdBefore}/${commId}?active_after=${activeAfter}&min_weight=${minWeight}`);
      const data = await res.json();

      // Render D3 Graph with sub-community colored bubbles
      graphViz.render(data);

      // Save state and render Sidebar Details including sub-communities
      activeCommunitySummary = data.community_summary;
      activeCommunityNodes = data.nodes;
      renderSidebarDetails(data.community_summary, data.nodes, data.sub_communities);
    } catch (err) {
      console.error('Failed to load community graph:', err);
      sidebarContent.innerHTML = '<div style="color:var(--accent-rose); padding:20px;">Failed to load graph data.</div>';
    }
  }

  function renderSidebarDetails(summary, nodes, subCommunities = []) {
    if (!summary) return;

    const geo = summary.geo_tag || { region: 'Global Cinema', flag: '🌐', primary_hub: 'International', geo_summary: '', regional_distribution: [] };

    const regDistHtml = (geo.regional_distribution || []).map(r => `
      <div class="genre-row" style="margin-bottom:6px;">
        <div class="genre-info">
          <span>${r.flag} ${r.region}</span>
          <span style="color:var(--accent-cyan); font-weight:700;">${r.percentage}%</span>
        </div>
        <div class="genre-bar-bg">
          <div class="genre-bar-fill" style="width: ${r.percentage}%; background: linear-gradient(90deg, #38bdf8, #818cf8);"></div>
        </div>
      </div>
    `).join('');

    const subCommHtml = (subCommunities || []).map(sc => `
      <div class="sub-comm-card-item" data-sub-id="${sc.sub_id}" style="border-left:4px solid ${sc.color}; background:rgba(255,255,255,0.03); padding:8px 12px; border-radius:6px; margin-bottom:6px; cursor:pointer;" title="Hover/Click to highlight this inner sub-community">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span style="font-weight:700; color:#fff; font-size:13px;">
            <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:${sc.color}; margin-right:6px;"></span>
            Sub-Circle #${sc.sub_id}
          </span>
          <span style="color:${sc.color}; font-weight:800; font-size:12px;">${sc.node_count} actors (${sc.percentage}%)</span>
        </div>
        <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">${sc.archetype}</div>
        <div style="font-size:11px; color:var(--text-dim); margin-top:3px;">
          Key Stars: ${(sc.top_actors || []).slice(0, 3).map(a => a.name).join(', ')}
        </div>
      </div>
    `).join('') || '<div style="color:var(--text-muted); font-size:12px;">No sub-communities detected.</div>';

    const bridgesHtml = (summary.bridges || []).map(b => 
      `<div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid rgba(255,255,255,0.05); font-size:13px;">
        <span>Bridge to Community #${b.target_community}</span>
        <span style="color:var(--accent-cyan); font-weight:700;">${b.connection_count} links</span>
      </div>`
    ).join('') || '<div style="color:var(--text-muted); font-size:12px;">No major inter-community bridges.</div>';

    const topMembersHtml = (nodes || []).slice(0, 15).map(n => 
      `<div class="actor-row-clickable" data-nconst="${n.id}" style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:4px; padding:4px 8px; background:rgba(255,255,255,0.03); border-radius:4px; cursor:pointer;" title="Click to view full actor statistics">
        <span style="color:#ffffff; font-weight:600;">
          <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${n.sub_community_color || '#38bdf8'}; margin-right:4px;"></span>
          ${n.label}
        </span>
        <span style="color:var(--accent-cyan); font-weight:700;">${n.degree} links</span>
      </div>`
    ).join('');

    const actorOptionsHtml = (nodes || []).map(n => 
      `<option value="${n.id}">${n.label} (${n.degree} links)</option>`
    ).join('');

    sidebarContent.innerHTML = `
      <div class="sidebar-section">
        <h4>Archetype</h4>
        <div style="font-size:18px; font-weight:700; color:#fff; margin-bottom:8px;">${summary.archetype}</div>
        <div style="font-size:13px; color:var(--text-muted);">Members: ${summary.node_count} | Intra Edges: ${summary.internal_edges}</div>
      </div>

      <div class="sidebar-section">
        <h4>🧩 Sub-Communities (Inner Circles)</h4>
        <div style="font-size:11px; color:var(--text-muted); margin-bottom:8px;">Hover or click a sub-community to filter network bubbles:</div>
        <div>${subCommHtml}</div>
      </div>

      <div class="sidebar-section">
        <h4>👤 Inspect Actor Statistics</h4>
        <select id="actor-select-dropdown" style="width:100%; margin-bottom:6px;">
          <option value="">-- Select Actor for Deep Dive --</option>
          ${actorOptionsHtml}
        </select>
        <div style="font-size:11px; color:var(--text-dim);">💡 Tip: Click any node circle in graph to view actor stats.</div>
      </div>

      <div class="sidebar-section">
        <h4>🌍 Geographical Profile</h4>
        <div style="font-size:15px; font-weight:700; color:#fff; margin-bottom:4px;">${geo.flag} ${geo.region}</div>
        <div style="font-size:12px; color:var(--accent-cyan); margin-bottom:8px;">📍 Hub: ${geo.primary_hub}</div>
        <div style="font-size:12px; color:var(--text-muted); margin-bottom:12px; line-height:1.4;">${geo.geo_summary}</div>
        <div style="font-size:12px; font-weight:600; color:var(--text-muted); margin-bottom:6px;">Regional Distribution:</div>
        <div>${regDistHtml}</div>
      </div>

      <div class="sidebar-section">
        <h4>Inter-Community Bridges</h4>
        <div>${bridgesHtml}</div>
      </div>

      <div class="sidebar-section">
        <h4>Top Central Members</h4>
        <div>${topMembersHtml}</div>
      </div>
    `;

    // Sub-Community Card Hover & Click Listeners
    sidebarContent.querySelectorAll('.sub-comm-card-item').forEach(el => {
      const subId = parseInt(el.getAttribute('data-sub-id'));
      el.addEventListener('mouseenter', () => {
        graphViz.highlightSubCommunity(subId);
      });
      el.addEventListener('mouseleave', () => {
        graphViz.highlightSubCommunity(null);
      });
      el.addEventListener('click', () => {
        graphViz.highlightSubCommunity(subId);
      });
    });

    // Dropdown Listener
    const dropdown = document.getElementById('actor-select-dropdown');
    if (dropdown) {
      dropdown.addEventListener('change', (e) => {
        if (e.target.value) fetchAndRenderActorStats(e.target.value);
      });
    }

    // Top Member Row Click Listeners
    sidebarContent.querySelectorAll('.actor-row-clickable').forEach(el => {
      el.addEventListener('click', () => {
        const nconst = el.getAttribute('data-nconst');
        if (nconst) fetchAndRenderActorStats(nconst);
      });
    });
  }

  async function fetchAndRenderActorStats(nconst) {
    sidebarContent.innerHTML = `<div style="color:var(--text-muted); padding:20px; text-align:center;">Fetching detailed statistics for actor...</div>`;

    try {
      const res = await fetch(`/api/actor/${nconst}`);
      const data = await res.json();
      renderActorStatsSidebar(data);
    } catch (err) {
      console.error('Failed to fetch actor stats:', err);
      sidebarContent.innerHTML = `<div style="color:var(--accent-rose); padding:20px;">Failed to load actor statistics.</div>`;
    }
  }

  function renderActorStatsSidebar(stats) {
    const geo = stats.geo_tag || { region: 'Global Cinema', flag: '🌐', primary_hub: 'International', geo_summary: '' };

    const genresHtml = (stats.genre_profile || []).map(g => `
      <div class="genre-row" style="margin-bottom:6px;">
        <div class="genre-info">
          <span>${g.genre}</span>
          <span style="color:var(--accent-cyan); font-weight:700;">${g.percentage}%</span>
        </div>
        <div class="genre-bar-bg">
          <div class="genre-bar-fill" style="width: ${g.percentage}%; background: linear-gradient(90deg, #34d399, #38bdf8);"></div>
        </div>
      </div>
    `).join('') || '<div style="color:var(--text-muted); font-size:12px;">No genre data available.</div>';

    const coStarsHtml = (stats.top_co_stars || []).map(cs => `
      <div class="actor-row-clickable" data-nconst="${cs.nconst}" style="display:flex; justify-content:space-between; font-size:12px; padding:6px 10px; background:rgba(56, 189, 248, 0.1); border:1px solid rgba(56, 189, 248, 0.2); border-radius:6px; margin-bottom:4px; cursor:pointer;" title="Click to view stats for ${cs.name}">
        <span style="color:#fff; font-weight:600;">🌟 ${cs.name}</span>
        <span style="color:var(--accent-amber); font-weight:700;">${cs.shared_movies_count} movies</span>
      </div>
    `).join('') || '<div style="color:var(--text-muted); font-size:12px;">No co-stars recorded.</div>';

    const filmographyHtml = (stats.top_movies || []).map(m => `
      <div style="font-size:12px; margin-bottom:8px; background:rgba(255,255,255,0.03); padding:6px 10px; border-radius:6px;">
        <div style="color:#fff; font-weight:700;">🎬 ${m.title} <span style="color:var(--accent-cyan);">(${m.year || 'N/A'})</span></div>
        <div style="font-size:11px; color:var(--text-muted);">${(m.genres || []).join(', ')}</div>
      </div>
    `).join('') || '<div style="color:var(--text-muted); font-size:12px;">No filmography recorded.</div>';

    sidebarContent.innerHTML = `
      <button id="btn-back-summary" class="btn-primary" style="padding:8px 14px; font-size:12px; margin-bottom:16px; width:100%; background:rgba(255,255,255,0.08); border:1px solid var(--border-color);">
        ⬅️ Back to Community Summary
      </button>

      <div class="sidebar-section">
        <h4 style="color:var(--accent-amber);">Actor Profile</h4>
        <div style="font-size:20px; font-weight:800; color:#fff; margin-bottom:2px;">${stats.name}</div>
        <div style="font-size:12px; color:var(--text-muted); margin-bottom:10px;">
          ${(stats.professions || []).map(p => p.toUpperCase()).join(' • ') || 'ACTOR'} | Active: ${stats.active_years}
        </div>
      </div>

      <div class="sidebar-section">
        <h4>🌍 Geographical Profile</h4>
        <div style="font-size:15px; font-weight:700; color:#fff; margin-bottom:2px;">${geo.flag} ${geo.region}</div>
        <div style="font-size:12px; color:var(--accent-cyan); margin-bottom:6px;">📍 Hub: ${geo.primary_hub}</div>
        <div style="font-size:12px; color:var(--text-muted); line-height:1.4;">${geo.geo_summary}</div>
      </div>

      <div class="sidebar-section">
        <h4>📊 Network Centrality Stats</h4>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; text-align:center;">
          <div style="background:rgba(255,255,255,0.04); padding:10px; border-radius:8px; border:1px solid rgba(255,255,255,0.06);">
            <div style="color:var(--accent-cyan); font-weight:800; font-size:18px;">${stats.network_stats.total_co_stars}</div>
            <div style="color:var(--text-muted); font-size:10px; text-transform:uppercase;">Co-Stars</div>
          </div>
          <div style="background:rgba(255,255,255,0.04); padding:10px; border-radius:8px; border:1px solid rgba(255,255,255,0.06);">
            <div style="color:var(--accent-purple); font-weight:800; font-size:18px;">${stats.network_stats.total_collaborations}</div>
            <div style="color:var(--text-muted); font-size:10px; text-transform:uppercase;">Collaborations</div>
          </div>
        </div>
      </div>

      <div class="sidebar-section">
        <h4>🎬 Genre Distribution</h4>
        <div>${genresHtml}</div>
      </div>

      <div class="sidebar-section">
        <h4>🤝 Top Collaborators</h4>
        <div>${coStarsHtml}</div>
      </div>

      <div class="sidebar-section">
        <h4>📽️ Notable Filmography</h4>
        <div>${filmographyHtml}</div>
      </div>
    `;

    document.getElementById('btn-back-summary').addEventListener('click', () => {
      if (activeCommunitySummary && activeCommunityNodes) {
        renderSidebarDetails(activeCommunitySummary, activeCommunityNodes);
      }
    });

    sidebarContent.querySelectorAll('.actor-row-clickable').forEach(el => {
      el.addEventListener('click', () => {
        const nconst = el.getAttribute('data-nconst');
        if (nconst) fetchAndRenderActorStats(nconst);
      });
    });
  }

  // Close Modal
  btnCloseModal.addEventListener('click', () => {
    modalOverlay.classList.remove('active');
  });

  modalOverlay.addEventListener('click', (e) => {
    if (e.target === modalOverlay) {
      modalOverlay.classList.remove('active');
    }
  });

  // Timeline View Logic
  const timelineYearSlider = document.getElementById('timeline-year-slider');
  const timelineYearValue = document.getElementById('timeline-year-value');
  const timelineDisplayYear = document.getElementById('timeline-display-year');
  const timelineResultsGrid = document.getElementById('timeline-results-grid');
  
  let timelineData = null;

  async function loadTimelineData() {
    try {
      const res = await fetch('/static/popular_actors_timeline.json');
      if (res.ok) {
        timelineData = await res.json();
        renderTimelineYear(parseInt(timelineYearSlider.value));
      } else {
        timelineResultsGrid.innerHTML = '<div style="color:var(--accent-rose); padding:20px;">Timeline data not available. Please run popularity_calculator.py first.</div>';
      }
    } catch (e) {
      console.error("Failed to load timeline data", e);
    }
  }
  
  function renderTimelineYear(year) {
    if (!timelineData) return;
    
    timelineDisplayYear.textContent = year;
    const yearData = timelineData.find(d => d.year === year);
    
    if (!yearData || !yearData.top_actors || yearData.top_actors.length === 0) {
      timelineResultsGrid.innerHTML = '<div style="color:var(--text-muted); padding:20px;">No data available for this year.</div>';
      return;
    }
    
    const html = yearData.top_actors.map((actor, idx) => `
      <div class="comm-card median-card" style="border-top: 4px solid var(--accent-purple);">
        <div class="median-rank" style="color: var(--accent-purple);">#${idx + 1}</div>
        <div class="median-name">${actor.name}</div>
        <div style="font-size:11px; color:var(--text-muted); margin-bottom:12px; text-transform:uppercase; letter-spacing:0.5px;">
          ${(actor.professions || []).join(' • ') || 'ACTOR'}
        </div>
        
        <div style="display:flex; flex-wrap:wrap; gap:8px; justify-content:center; margin-bottom:16px;">
          <span class="median-path" style="background:rgba(168, 85, 247, 0.15); color:var(--accent-purple);">Popularity Score: ${actor.score}</span>
          <span class="median-path" style="background:rgba(251, 191, 36, 0.15); color:var(--accent-amber);">Movies in Window (${yearData.window}): ${actor.movies_in_window}</span>
        </div>
      </div>
    `).join('');
    
    timelineResultsGrid.innerHTML = html;
  }
  
  timelineYearSlider.addEventListener('input', (e) => {
    const yr = parseInt(e.target.value);
    timelineYearValue.textContent = yr;
    renderTimelineYear(yr);
  });
  
  // Load timeline data when user switches to the timeline tab
  document.querySelector('.tab-btn[data-target="timeline-view"]').addEventListener('click', () => {
    if (!timelineData) {
      loadTimelineData();
    }
  });
});
