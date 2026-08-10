/* D3 Force-Directed Graph Simulation Engine */

class CommunityGraphViz {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.svg = null;
    this.simulation = null;
    this.width = 0;
    this.height = 0;
    this.onNodeClick = null;
  }

  setNodeClickListener(callback) {
    this.onNodeClick = callback;
  }

  init() {
    this.container.innerHTML = '';
    this.width = this.container.clientWidth || 800;
    this.height = this.container.clientHeight || 600;

    this.svg = d3.select(this.container)
      .append('svg')
      .attr('width', '100%')
      .attr('height', '100%')
      .attr('viewBox', `0 0 ${this.width} ${this.height}`);

    // Add zoom behavior
    const g = this.svg.append('g').attr('class', 'main-group');
    
    const zoom = d3.zoom()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    this.svg.call(zoom);
    this.g = g;
  }

  render(data) {
    this.init();
    if (!data || !data.nodes || data.nodes.length === 0) {
      this.container.innerHTML = '<div style="color:#9ca3af; padding:40px; text-align:center;">No graph nodes available.</div>';
      return;
    }

    const nodes = data.nodes.map(d => ({ ...d }));
    const edges = data.edges.map(d => ({ ...d }));

    // Create force simulation
    this.simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(edges).id(d => d.id).distance(60))
      .force('charge', d3.forceManyBody().strength(-180))
      .force('center', d3.forceCenter(this.width / 2, this.height / 2))
      .force('collision', d3.forceCollide().radius(d => Math.sqrt(d.degree || 1) * 3 + 8));

    // Render Edges
    const link = this.g.append('g')
      .selectAll('line')
      .data(edges)
      .enter()
      .append('line')
      .attr('stroke', 'rgba(129, 140, 248, 0.25)')
      .attr('stroke-width', d => Math.min(Math.sqrt(d.weight || 1), 5));

    // Render Nodes
    const node = this.g.append('g')
      .selectAll('g.node-group')
      .data(nodes)
      .enter()
      .append('g')
      .attr('class', 'node-group')
      .call(d3.drag()
        .on('start', (event, d) => this.dragstarted(event, d))
        .on('drag', (event, d) => this.dragged(event, d))
        .on('end', (event, d) => this.dragended(event, d))
      );

    node.style('cursor', 'pointer')
      .on('click', (event, d) => {
        event.stopPropagation();
        node.selectAll('circle')
          .attr('stroke', n => n.id === d.id ? '#fbbf24' : '#ffffff')
          .attr('stroke-width', n => n.id === d.id ? 3.5 : 1.5);
        if (this.onNodeClick) {
          this.onNodeClick(d);
        }
      });

    node.append('circle')
      .attr('r', d => Math.max(Math.sqrt(d.degree || 1) * 3 + 4, 5))
      .attr('fill', d => d.sub_community_color || '#38bdf8')
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 1.5)
      .style('filter', d => `drop-shadow(0 0 6px ${d.sub_community_color || '#38bdf8'})`);

    // Labels
    node.append('text')
      .text(d => d.label)
      .attr('x', 12)
      .attr('y', 4)
      .attr('fill', '#f3f4f6')
      .attr('font-size', '11px')
      .attr('font-weight', '500')
      .style('pointer-events', 'none');

    // Title / Tooltip
    node.append('title')
      .text(d => `${d.label} (Sub-Community #${d.sub_community_id || 1})\nDegree: ${d.degree}\nProfessions: ${d.professions ? d.professions.join(', ') : 'None'}`);

    this.simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

      node
        .attr('transform', d => `translate(${d.x},${d.y})`);
    });
  }

  dragstarted(event, d) {
    if (!event.active) this.simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
  }

  dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
  }

  dragended(event, d) {
    if (!event.active) this.simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
  }

  highlightSubCommunity(subId) {
    if (!this.g) return;
    if (!subId) {
      this.g.selectAll('g.node-group').style('opacity', 1);
      this.g.selectAll('line').style('opacity', 1);
      return;
    }

    this.g.selectAll('g.node-group')
      .style('opacity', d => (d.sub_community_id === subId) ? 1 : 0.12);

    this.g.selectAll('line')
      .style('opacity', e => (e.source.sub_community_id === subId && e.target.sub_community_id === subId) ? 0.9 : 0.06);
  }
}
