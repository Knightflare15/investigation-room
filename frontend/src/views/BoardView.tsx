import { useCallback, useState } from 'react';
import {
  type Edge,
  type Node,
  Background,
  Controls,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { BoardLinkResponse, CaseDetailResponse, PlayerCaseState } from '../types';
import { PanelHeader } from '../ui';

type BoardNode = { id: string; label: string };

type Props = {
  caseDetail: CaseDetailResponse;
  saveState: PlayerCaseState;
  boardNodes: BoardNode[];
  onBoardLink: (source: string, target: string, linkType: string, notes: string) => Promise<BoardLinkResponse>;
};

const nodeStyle = {
  background: '#1a1614',
  color: '#e5e0d5',
  border: '1px solid #4a4035',
  borderRadius: 4,
  fontSize: 12,
  padding: '6px 10px',
};

function toFlowNodes(boardNodes: BoardNode[]): Node[] {
  return boardNodes.map((node, i) => ({
    id: node.id,
    data: { label: node.label },
    position: { x: 100 + (i % 4) * 220, y: 80 + Math.floor(i / 4) * 130 },
    type: node.id === 'victim' ? 'input' : 'default',
    style: nodeStyle,
  }));
}

function toFlowEdges(boardLinks: string[]): Edge[] {
  return boardLinks.map((link) => ({
    id: link,
    source: 'victim',
    target: link.split('-')[1] ?? '',
    label: link,
    animated: true,
    style: { stroke: '#4ade80' },
  }));
}

export default function BoardView({ caseDetail, saveState, boardNodes, onBoardLink }: Props) {
  const [nodes, , onNodesChange] = useNodesState(toFlowNodes(boardNodes));
  const [edges, setEdges, onEdgesChange] = useEdgesState(toFlowEdges(saveState.board_links));

  const [boardSource, setBoardSource] = useState(boardNodes[0]?.id ?? '');
  const [boardTarget, setBoardTarget] = useState(boardNodes[1]?.id ?? '');
  const [boardType, setBoardType] = useState('secret-meeting');
  const [boardFeedback, setBoardFeedback] = useState('');

  const opportunityPct = Math.min(100, 35 + caseDetail.documents.length * 8);
  const motivePct = Math.min(100, 22 + saveState.discovered_contexts.length * 7);
  const meansPct = Math.min(100, 18 + saveState.pinned_evidence_ids.length * 12);
  const truthPct = Math.min(100, 20 + saveState.board_links.length * 11);

  const handleValidate = useCallback(async () => {
    try {
      const response = await onBoardLink(boardSource, boardTarget, boardType, boardType);
      if (response.is_valid) {
        const linkId = response.link_id;
        setEdges((eds) => [
          ...eds,
          {
            id: linkId,
            source: boardSource,
            target: boardTarget,
            label: boardType,
            animated: true,
            style: { stroke: '#4ade80' },
          },
        ]);
        setBoardFeedback(
          `Validated. New threads: ${[...response.unlocked_documents, ...response.unlocked_suspects].join(', ') || 'none'}`,
        );
      } else {
        setEdges((eds) => [
          ...eds,
          {
            id: `unconfirmed-${Date.now()}`,
            source: boardSource,
            target: boardTarget,
            label: boardType,
            animated: false,
            style: { stroke: '#f59e0b' },
          },
        ]);
        setBoardFeedback('The deduction has been logged, but the board still needs stronger support.');
      }
    } catch (e) {
      setBoardFeedback((e as Error).message);
    }
  }, [boardSource, boardTarget, boardType, onBoardLink, setEdges]);

  return (
    <section className="dossier-surface">
      <PanelHeader
        eyebrow="Evidence Board"
        title="Theory Progress"
        subtitle="Connect motives, means, opportunity, and contradiction pressure into one stable accusation."
      />
      <div className="board-layout">
        <article className="theory-graph-card" style={{ height: 420 }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            fitView
          >
            <Background color="#2a2520" gap={20} />
            <Controls />
          </ReactFlow>
        </article>

        <div className="board-side-column">
          <section className="intel-card">
            <div className="intel-card-header">
              <span>Theory Strength</span>
            </div>
            <div className="theory-orbit" style={{ fontSize: 13, gap: 8, display: 'flex', flexDirection: 'column' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Opportunity</span><strong>{opportunityPct}%</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Motive</span><strong>{motivePct}%</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Means</span><strong>{meansPct}%</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Truth</span><strong>{truthPct}%</strong>
              </div>
            </div>
          </section>

          <section className="intel-card">
            <div className="intel-card-header">
              <span>Validate New Link</span>
              <strong>Board Tool</strong>
            </div>
            <div className="board-form">
              <select value={boardSource} onChange={(e) => setBoardSource(e.target.value)}>
                {boardNodes.map((node) => (
                  <option key={`src-${node.id}`} value={node.id}>{node.label}</option>
                ))}
              </select>
              <select value={boardTarget} onChange={(e) => setBoardTarget(e.target.value)}>
                {boardNodes.map((node) => (
                  <option key={`target-${node.id}`} value={node.id}>{node.label}</option>
                ))}
              </select>
              <input value={boardType} onChange={(e) => setBoardType(e.target.value)} placeholder="link type" />
              <button className="dossier-button dossier-button-accent" type="button" onClick={handleValidate}>
                Validate Deduction
              </button>
            </div>
            {boardFeedback ? <p className="board-feedback">{boardFeedback}</p> : null}
          </section>

          <section className="intel-card">
            <div className="intel-card-header">
              <span>Confirmed Links</span>
              <strong>{saveState.board_links.length.toString().padStart(2, '0')}</strong>
            </div>
            <div className="board-links">
              {saveState.board_links.map((link) => (
                <div key={link} className="board-link-card">{link}</div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}
