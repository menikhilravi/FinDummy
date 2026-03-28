"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Zap, AlertTriangle, CheckCircle } from "lucide-react";
import { emergencyShutdown } from "@/lib/api";
import { useTradeStore } from "@/hooks/useTradeStore";
import { cn } from "@/lib/utils";

type Phase = "idle" | "confirm" | "executing" | "done" | "error";

export function PanicButton() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [message, setMessage] = useState("");
  const setAgentRunning = useTradeStore((s) => s.setAgentRunning);

  const handleClick = async () => {
    if (phase === "idle") {
      setPhase("confirm");
      return;
    }

    if (phase === "confirm") {
      setPhase("executing");
      try {
        const result = await emergencyShutdown();
        setMessage(result.message);
        setAgentRunning(false);
        setPhase("done");
      } catch (err: any) {
        setMessage(err.message ?? "Shutdown request failed.");
        setPhase("error");
      }
      return;
    }

    if (phase === "done" || phase === "error") {
      setPhase("idle");
      setMessage("");
    }
  };

  const handleCancel = () => {
    setPhase("idle");
  };

  return (
    <div className="flex flex-col items-center gap-3">
      <AnimatePresence mode="wait">
        {phase === "confirm" && (
          <motion.div
            key="confirm-msg"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="text-center"
          >
            <p className="text-xs font-mono text-neon-red font-semibold">
              ⚠ CLOSE ALL POSITIONS?
            </p>
            <p className="text-[10px] font-mono text-text-muted mt-0.5">
              This will cancel orders and liquidate everything.
            </p>
          </motion.div>
        )}

        {phase === "done" && (
          <motion.div
            key="done-msg"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-1.5 text-neon-green text-xs font-mono"
          >
            <CheckCircle className="w-3.5 h-3.5" />
            Shutdown complete
          </motion.div>
        )}

        {phase === "error" && (
          <motion.div
            key="err-msg"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-1.5 text-neon-red text-xs font-mono"
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            {message}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex gap-2 items-center">
        {/* Main panic button */}
        <motion.button
          onClick={handleClick}
          disabled={phase === "executing"}
          whileTap={{ scale: 0.95 }}
          className={cn(
            "relative group flex items-center gap-2 px-6 py-3 rounded-xl",
            "font-mono font-bold text-sm uppercase tracking-widest",
            "border-2 transition-all duration-200",
            phase === "idle" &&
              "bg-neon-red/10 border-neon-red/50 text-neon-red hover:bg-neon-red/20 hover:border-neon-red hover:shadow-neon-red",
            phase === "confirm" &&
              "bg-neon-red border-neon-red text-bg-base animate-pulse",
            phase === "executing" &&
              "bg-neon-red/5 border-neon-red/20 text-neon-red/40 cursor-not-allowed",
            phase === "done" &&
              "bg-neon-green/10 border-neon-green/50 text-neon-green",
            phase === "error" &&
              "bg-neon-red/10 border-neon-red/50 text-neon-red"
          )}
        >
          {/* Pulse ring */}
          {phase === "idle" && (
            <span className="absolute inset-0 rounded-xl border-2 border-neon-red/30 animate-ping opacity-30" />
          )}

          <Zap
            className={cn(
              "w-4 h-4",
              phase === "executing" && "animate-spin"
            )}
          />
          {phase === "idle" && "PANIC"}
          {phase === "confirm" && "CONFIRM KILL"}
          {phase === "executing" && "SHUTTING DOWN…"}
          {phase === "done" && "DONE"}
          {phase === "error" && "RETRY"}
        </motion.button>

        {/* Cancel button (only during confirm) */}
        <AnimatePresence>
          {phase === "confirm" && (
            <motion.button
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              onClick={handleCancel}
              className="px-4 py-3 rounded-xl font-mono text-sm text-text-muted border border-bg-border hover:border-text-muted transition-colors"
            >
              CANCEL
            </motion.button>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
