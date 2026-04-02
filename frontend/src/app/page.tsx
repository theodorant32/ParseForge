"use client";

import { useState, useEffect } from "react";
import { 
  Play, 
  Terminal, 
  BrainCircuit, 
  ScanSearch, 
  FileText,
  CheckCircle2,
  AlertCircle,
  Network,
  Cpu,
  Layers,
  Settings2,
  Copy,
  Activity
} from "lucide-react";
import styles from "./page.module.css";

type StageData = {
  status: string;
  duration_ms: number;
};

type PipelineResult = {
  success: boolean;
  trace_id: string;
  input: string;
  parsed_request?: any;
  validation_result?: any;
  decision?: any;
  error?: { message: string };
  stages: Record<string, StageData> | any[];
};

export default function Home() {
  const [inputText, setInputText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [visualStage, setVisualStage] = useState(-1);
  const [copied, setCopied] = useState(false);

  const handleSubmit = async () => {
    if (!inputText.trim()) return;

    setLoading(true);
    setResult(null);
    setVisualStage(0);

    try {
      // Simulate fake pipeline step delays for frontend UX before API returns
      setTimeout(() => setVisualStage(1), 300);
      setTimeout(() => setVisualStage(2), 600);

      const response = await fetch("http://127.0.0.1:8000/pipeline/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: inputText }),
      });

      const data = await response.json();
      setResult(data);
      setVisualStage(4);
    } catch (error) {
      console.error(error);
      setResult({
        success: false,
        trace_id: "local-error",
        input: inputText,
        stages: [],
        error: { message: "Failed to connect to backend service. Ensure API is running." }
      });
      setVisualStage(4);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    }
  };

  const copyJson = () => {
    if (result) {
      navigator.clipboard.writeText(JSON.stringify(result, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // Pipeline Flow Logic
  const getStageClass = (index: number, stageName: string) => {
    if (loading && visualStage === index) return `${styles.stepNode} ${styles.stepPending}`;
    
    // If we've passed this stage visually or via real data
    if (visualStage > index || (result && result.success)) return `${styles.stepNode} ${styles.stepSuccess}`;
    
    // Check real error state
    if (result && !result.success) {
       // Deeply check if it failed at this stage
       const stages = result.stages || [];
       if (Array.isArray(stages)) {
           const stageInfo = stages.find(s => s.stage === stageName);
           if (stageInfo && stageInfo.status === "failed") return `${styles.stepNode} ${styles.stepError}`;
       }
       // If earlier array check didn't hit, default to error if pipeline failed generally on last step
       if (visualStage >= index) return `${styles.stepNode} ${styles.stepError}`;
    }

    return styles.stepNode;
  };

  // Dynamic progress bar width
  const getTrackFillWidth = () => {
    if (visualStage === -1) return "0%";
    if (visualStage === 0) return "10%";
    if (visualStage === 1) return "40%";
    if (visualStage === 2) return "75%";
    if (visualStage >= 3) return "100%";
    return "0%";
  };

  return (
    <div className={styles.layout}>
      {/* 1. App Navigation Bar */}
      <nav className={styles.appNavbar}>
        <div className={styles.navContent}>
          <div className={styles.brand}>
            <div className={styles.logoMark}><Network size={16} /></div>
            <div>
              <h1 className={styles.title}>ParseForge Dashboard</h1>
            </div>
          </div>
          <div className={styles.navLinks}>
            <button className={styles.iconButton} aria-label="Settings"><Settings2 size={18} /></button>
          </div>
        </div>
      </nav>

      {/* 2. Main Work Area */}
      <main className={styles.mainGrid}>
        
        {/* TOP ROW: Command Palette & Execution Tracker */}
        <div className={styles.controlPanel}>
          
          <div className={styles.editorContainer}>
            <textarea
              className={styles.inputArea}
              placeholder="Enter unstructured text data stream... (Press Cmd+Enter to execute code)"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
              spellCheck={false}
            />
            <div className={styles.editorToolbar}>
              <div className={styles.toolbarLeft}>
                 <button className={styles.toolbarAction} title="Add Context"><FileText size={16} /></button>
              </div>
              <button 
                className={styles.buttonSubmit} 
                onClick={handleSubmit}
                disabled={loading || !inputText.trim()}
              >
                {loading ? <div className={styles.statusDotActive} style={{width: 8, height: 8}} /> : <Play size={14} fill="white" />}
                {loading ? "Processing..." : "Execute"}
              </button>
            </div>
          </div>

          <div className={styles.pipelineContainer}>
            <div className={styles.pipelineHeader}>
              <h2><Cpu size={16} /> Pipeline Tracker</h2>
              <div className={styles.statusIndicator}>
                {loading ? <div className={styles.statusDotActive} /> : <div className={styles.statusDot} />}
                {loading ? "Computing" : result ? "Finished" : "Idle"}
              </div>
            </div>

            <div className={styles.pipelineTrackWrapper}>
              <div className={styles.trackBackground}></div>
              <div className={styles.trackFill} style={{ width: getTrackFillWidth() }}></div>
              
              <div className={getStageClass(0, "input")}>
                <div className={styles.stepIconBox}><Terminal size={18} /></div>
                <span className={styles.stepLabel}>Ingest</span>
              </div>

              <div className={getStageClass(1, "parser")}>
                <div className={styles.stepIconBox}><Layers size={18} /></div>
                <span className={styles.stepLabel}>Parse</span>
              </div>

              <div className={getStageClass(2, "validator")}>
                <div className={styles.stepIconBox}><ScanSearch size={18} /></div>
                <span className={styles.stepLabel}>Validate</span>
              </div>

              <div className={getStageClass(3, "decision_engine")}>
                <div className={styles.stepIconBox}><BrainCircuit size={18} /></div>
                <span className={styles.stepLabel}>Route</span>
              </div>
            </div>
          </div>
          
        </div>

        {/* BOTTOM ROW: Smooth Data Panels & Empty States */}
        {result ? (
          <div className={`${styles.dataPanel} ${styles.fadeInUp}`}>
            
            <div className={styles.outputCard}>
              <div className={styles.outputHeader}>
                <h3><Activity size={16} /> Analysis Report</h3>
                {result.success && <span className={styles.traceId}>ID: {result.trace_id}</span>}
              </div>

              <div className={styles.decisionLayout}>
                {result.success ? (
                  <>
                    <div className={styles.decisionHeaderBlock}>
                      <div className={styles.scoreWrapper}>
                        <span className={styles.scoreValue}>{result.decision?.score} <span className={styles.scoreMax}>/ 100</span></span>
                        <span className={styles.scoreLabel}>Confidence Score</span>
                      </div>
                      <div className={`${styles.actionBadge} ${styles[`action${result.decision?.action?.toUpperCase()}`]}`}>
                        <CheckCircle2 size={14} />
                        {result.decision?.action?.toUpperCase()}
                      </div>
                    </div>

                    <div className={styles.reasonBox}>
                       <span className={styles.reasonLabel}>Trace Route Factors</span>
                       {(() => {
                          const rawReason = result.decision?.reason || "";
                          const braceMatch = rawReason.match(/\[(.*?)\]/);
                          let factors: string[] = [];
                          let pureReason = rawReason;
                          
                          if (braceMatch) {
                            factors = braceMatch[1].split(',').map((s: string) => s.trim());
                            pureReason = rawReason.replace(/Score \d+\/\d+ \[.*?\]\.?\s*/, "").replace(/^.*\]\.\s*/, "");
                          }

                          return (
                            <div className={styles.routeContainer}>
                                {factors.length > 0 && (
                                  <div className={styles.factorList}>
                                    {factors.map((f, i) => (
                                      <span key={i} className={styles.factorTag}>{f}</span>
                                    ))}
                                  </div>
                                )}
                                <p className={styles.pureReason}>{pureReason}</p>
                            </div>
                          );
                       })()}
                    </div>

                    <div className={styles.dataList}>
                      <div className={styles.dataRow}>
                        <span className={styles.dataKey}><BrainCircuit size={14}/> Identified Intent</span>
                        <span className={styles.dataValue}>{result.parsed_request?.intent}</span>
                      </div>
                      <div className={styles.dataRow}>
                        <span className={styles.dataKey}><Layers size={14}/> Derived Topic</span>
                        <span className={styles.dataValue}>{result.parsed_request?.topic}</span>
                      </div>
                      <div className={styles.dataRow}>
                        <span className={styles.dataKey}><Activity size={14}/> Assessed Urgency</span>
                        <span className={styles.dataValue}>{result.parsed_request?.urgency || "None"}</span>
                      </div>
                    </div>
                  </>
                ) : (
                  <>
                    <div className={styles.decisionHeaderBlock}>
                        <div className={styles.scoreWrapper}>
                          <span className={styles.scoreValue} style={{color: 'var(--error)'}}>Failed</span>
                          <span className={styles.scoreLabel}>Pipeline execution halted</span>
                        </div>
                        <div className={`${styles.actionBadge} ${styles.actionREJECT}`}>
                          <AlertCircle size={14} />
                          REJECTED
                        </div>
                    </div>

                    <div className={`${styles.reasonBox} ${styles.reasonBoxError}`}>
                       <span className={styles.reasonLabel} style={{color: '#991b1b'}}>Fatal Validation Exception</span>
                       {result.error?.message || "Internal unknown exception detected at runtime."}
                    </div>
                  </>
                )}
              </div>
            </div>

            <div className={styles.outputCard}>
              <div className={styles.outputHeader}>
                <h3><Terminal size={16} /> JSON Payload</h3>
                <button 
                  className={styles.buttonGhost} 
                  onClick={copyJson} 
                  aria-label="Copy to Clipboard"
                >
                  {copied ? <><CheckCircle2 size={14} color="var(--success)"/> Copied!</> : <><Copy size={14} /> Copy</>}
                </button>
              </div>
              <div className={styles.terminalContainer}>
                <pre>{JSON.stringify(result, null, 2)}</pre>
              </div>
            </div>

          </div>
        ) : (
          <div className={`${styles.emptyStateContainer} ${loading ? styles.shimmer : ''}`}>
             <div className={styles.emptyStateContent}>
               {loading ? (
                  <>
                     <div className={styles.skeletonIcon}></div>
                     <div className={styles.skeletonTextTitle}></div>
                     <div className={styles.skeletonTextBody}></div>
                  </>
               ) : (
                 <>
                   <DatabaseIcon className={styles.emptyIcon} size={48} />
                   <h3>Awaiting Data Stream</h3>
                   <p>Initialize a pipeline execution to populate telemetry.</p>
                 </>
               )}
             </div>
          </div>
        )}

      </main>
    </div>
  );
}

// Inline DB icon since we can't export directly in the map quickly
function DatabaseIcon(props: any) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={props.size} height={props.size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={props.className}>
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M3 5V19A9 3 0 0 0 21 19V5" />
      <path d="M3 12A9 3 0 0 0 21 12" />
    </svg>
  );
}
