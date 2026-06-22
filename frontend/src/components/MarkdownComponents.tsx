import React, { useState } from "react";
import { Database } from "lucide-react";

export const TimelineWidget = ({ jsonStr, onAction }: { jsonStr: string, onAction: (msg: string) => void }) => {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [submittedState, setSubmittedState] = useState<string | null>(null);
  
  let items = [];
  try { items = JSON.parse(jsonStr); } catch (e) {}

  if (submittedState === 'cancelled') {
    return <div className="timeline-marker cancelled">❌ Action Cancelled</div>;
  }
  if (submittedState) {
    const selectedItem = items.find((i: any) => i.id === submittedState);
    return <div className="timeline-marker restored">⏪ Restored to: {selectedItem?.desc || submittedState}</div>;
  }

  return (
    <div className="timeline-glass-box">
      <div className="timeline-header">
        <Database size={16} style={{marginRight: '8px', color: '#60a5fa'}} />
        Interactive Database Timeline
      </div>
      <div className="timeline-list">
        {items.map((item: any) => (
          <div 
            key={item.id} 
            className={`timeline-item ${selectedId === item.id ? 'selected' : ''}`}
            onClick={() => setSelectedId(item.id)}
          >
            <div className="timeline-date">{item.date}</div>
            <div className="timeline-desc">{item.desc}</div>
          </div>
        ))}
      </div>
      <div className="timeline-footer">
        <button 
          className="timeline-btn cancel" 
          onClick={() => setSubmittedState('cancelled')}
        >
          Cancel
        </button>
        <button 
          className={`timeline-btn restore ${selectedId ? 'active' : ''}`}
          disabled={!selectedId}
          onClick={() => {
            if (selectedId) {
              setSubmittedState(selectedId);
              onAction("restore_" + selectedId);
            }
          }}
        >
          Restore State
        </button>
      </div>
    </div>
  );
};

export const getMarkdownComponents = (onAction: (msg: string) => void) => ({
  a: ({ node, ...props }: any) => {
    if (props.href?.startsWith("#action-")) {
      const actionName = props.children?.toString().toLowerCase() || "";
      let bg = "rgba(0, 112, 243, 0.2)";
      let border = "1px solid rgba(0, 112, 243, 0.5)";
      if (actionName.includes("yes")) {
        bg = "rgba(16, 185, 129, 0.2)";
        border = "1px solid rgba(16, 185, 129, 0.5)";
      } else if (actionName.includes("no")) {
        bg = "rgba(239, 68, 68, 0.2)";
        border = "1px solid rgba(239, 68, 68, 0.5)";
      }
      return (
        <button 
          style={{ backgroundColor: bg, border: border, backdropFilter: 'blur(8px)', color: 'white', padding: '8px 16px', borderRadius: '8px', cursor: 'pointer', margin: '8px 8px 4px 0', fontWeight: 600, fontSize: '0.9rem', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
          onClick={(e) => { e.preventDefault(); if (onAction) onAction(props.children as string); }}
        >
          {props.children}
        </button>
      );
    }
    return <a {...props} />;
  },
  code: ({ node, inline, className, children, ...props }: any) => {
    const match = /language-(\w+)/.exec(className || '');
    if (!inline && match && match[1] === 'timeline') {
      return <TimelineWidget jsonStr={String(children).replace(/\n$/, '')} onAction={onAction} />;
    }
    return <code className={className} {...props}>{children}</code>;
  }
});
