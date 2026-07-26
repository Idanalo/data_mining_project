/* Main Frontend Application Logic */

document.addEventListener('DOMContentLoaded', () => {
  const yearSlider = document.getElementById('year-slider');
  const yearValue = document.getElementById('year-value');
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

  // Sync Slider Value Display
  yearSlider.addEventListener('input', (e) => {
    yearValue.textContent = e.target.value;
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
      yearSlider.value = data.default_year;
      yearValue.textContent = data.default_year;
    } catch (err) {
      console.error('Failed to fetch years:', err);
    }
  }

  async function runClustering() {
    const year = parseInt(yearSlider.value);
    const minWeight = parseInt(minWeightSelect.value);
    const maxCommunities = parseInt(maxCommSelect.value);

    btnRun.innerHTML = '⚡ Computing Graph...';
    btnRun.disabled = true;

    try {
      const res = await fetch('/api/cluster', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          year: year,
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

  // Open Community Modal & Fetch Graph
  async function openCommunityModal(commId) {
    const year = parseInt(yearSlider.value);
    const minWeight = parseInt(minWeightSelect.value);

    modalTitle.textContent = `Community #${commId} Inspection & Bridges`;
    modalOverlay.classList.add('active');

    sidebarContent.innerHTML = '<div style="color:var(--text-muted);">Loading community subgraph...</div>';

    try {
      const res = await fetch(`/api/community/${year}/${commId}?min_weight=${minWeight}`);
      const data = await res.json();

      // Render D3 Graph
      graphViz.render(data);

      // Render Sidebar Details
      renderSidebarDetails(data.community_summary, data.nodes);
    } catch (err) {
      console.error('Failed to load community graph:', err);
      sidebarContent.innerHTML = '<div style="color:var(--accent-rose);">Failed to load graph data.</div>';
    }
  }

  function renderSidebarDetails(summary, nodes) {
    if (!summary) return;

    const bridgesHtml = (summary.bridges || []).map(b => 
      `<div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid rgba(255,255,255,0.05); font-size:13px;">
        <span>Bridge to Community #${b.target_community}</span>
        <span style="color:var(--accent-cyan); font-weight:700;">${b.connection_count} links</span>
      </div>`
    ).join('') || '<div style="color:var(--text-muted); font-size:12px;">No major inter-community bridges.</div>';

    const topMembersHtml = (nodes || []).slice(0, 15).map(n => 
      `<div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:4px;">
        <span style="color:#ffffff;">${n.label}</span>
        <span style="color:var(--text-muted);">${n.degree} connections</span>
      </div>`
    ).join('');

    sidebarContent.innerHTML = `
      <div class="sidebar-section">
        <h4>Archetype</h4>
        <div style="font-size:18px; font-weight:700; color:#fff; margin-bottom:8px;">${summary.archetype}</div>
        <div style="font-size:13px; color:var(--text-muted);">Members: ${summary.node_count} | Intra Edges: ${summary.internal_edges}</div>
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
});
