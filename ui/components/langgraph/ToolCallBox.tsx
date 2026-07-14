"use client";
// FIXME  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlZCTmVnPT06OWI1ODc5MjA=

import React, {
  useState,
  useMemo,
  useCallback,
  memo,
  useDeferredValue,
  useEffect,
} from "react";
import {
  ChevronDown,
  ChevronUp,
  Terminal,
  AlertCircle,
  Loader2,
  CircleCheckBigIcon,
  StopCircle,
  Download,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ToolCall, ActionRequest, ReviewConfig } from "@/lib/langgraph/types";
import { cn } from "@/lib/utils";
import { LoadExternalComponent } from "@langchain/langgraph-sdk/react-ui";
import { ToolApprovalInterrupt } from "@/components/langgraph/ToolApprovalInterrupt";
import { downloadAgentFile } from "@/lib/api/agentFiles";

interface ArgItemProps {
  argKey: string;
  value: any;
  isExpanded?: boolean;
  onToggle: (key: string) => void;
}

const ArgItem = memo<ArgItemProps>(({ argKey, value, isExpanded, onToggle }) => {
  const serializedValue = useMemo(() => {
    if (!isExpanded) return "";
    if (typeof value === "string") {
      return value;
    }
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }, [isExpanded, value]);

  return (
    <div className="rounded-sm border border-border">
      <button
        onClick={() => onToggle(argKey)}
        className="flex w-full items-center justify-between bg-muted/30 p-2 text-left text-xs font-medium transition-colors hover:bg-muted/50"
      >
        <span className="font-mono">{argKey}</span>
        {isExpanded ? (
          <ChevronUp size={12} className="text-muted-foreground" />
        ) : (
          <ChevronDown size={12} className="text-muted-foreground" />
        )}
      </button>
      {isExpanded && (
        <div className="border-t border-border bg-muted/20 p-2 max-h-96 overflow-y-auto">
          <pre className="m-0 overflow-x-auto whitespace-pre font-mono text-xs leading-6 text-foreground">
            {serializedValue}
          </pre>
        </div>
      )}
    </div>
  );
});
// eslint-disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlZCTmVnPT06OWI1ODc5MjA=

ArgItem.displayName = "ArgItem";

interface ToolCallBoxProps {
  toolCall: ToolCall;
  uiComponent?: any;
  stream?: any;
  graphId?: string;
  actionRequest?: ActionRequest;
  reviewConfig?: ReviewConfig;
  onResume?: (value: any) => void;
  isLoading?: boolean;
  isResumingInterrupt?: boolean;
}
// WATERMARK  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlZCTmVnPT06OWI1ODc5MjA=

export const ToolCallBox = React.memo<ToolCallBoxProps>(
  ({
    toolCall,
    uiComponent,
    stream,
    graphId,
    actionRequest,
    reviewConfig,
    onResume,
    isLoading,
    isResumingInterrupt,
  }) => {
    const { name, args, result, status } = useMemo(() => {
      return {
        name: toolCall.name || "Unknown Tool",
        args: toolCall.args || {},
        result: toolCall.result,
        status: toolCall.status || "completed",
      };
    }, [toolCall.name, toolCall.args, toolCall.result, toolCall.status]);

    const isExcelExport = name === "export_test_cases_to_excel";
    const hasDownloadableResult =
      typeof result === "string" && result.startsWith("/");

    const [isExpanded, setIsExpanded] = useState(
      () =>
        !!uiComponent ||
        !!actionRequest ||
        (isExcelExport && hasDownloadableResult)
    );

    // 当 Excel 导出结果到达后自动展开工具调用框，方便用户看到下载按钮
    useEffect(() => {
      if (isExcelExport && hasDownloadableResult) {
        setIsExpanded(true);
      }
    }, [isExcelExport, hasDownloadableResult]);
    const [expandedArgs, setExpandedArgs] = useState<Record<string, boolean>>(
      {}
    );

    const argsKeys = useMemo(() => Object.keys(args), [args]);
    const argsEntries = useMemo(() => Object.entries(args), [args]);
    const hasContent = useMemo(
      () => result || argsKeys.length > 0,
      [result, argsKeys.length]
    );

    const deferredResult = useDeferredValue(result);

    const serializedResult = useMemo(() => {
      if (!deferredResult) return "";
      if (typeof deferredResult === "string") {
        return deferredResult;
      }
      try {
        return JSON.stringify(deferredResult, null, 2);
      } catch {
        return String(deferredResult);
      }
    }, [deferredResult]);

    const toggleExpanded = useCallback(() => {
      setIsExpanded((prev) => !prev);
    }, []);

    const toggleArgExpanded = useCallback((argKey: string) => {
      setExpandedArgs((prev) => ({
        ...prev,
        [argKey]: !prev[argKey],
      }));
    }, []);

    const statusIcon = useMemo(() => {
      switch (status) {
        case "completed":
          return <CircleCheckBigIcon />;
        case "error":
          return (
            <AlertCircle
              size={14}
              className="text-destructive"
            />
          );
        case "pending":
          return (
            <Loader2
              size={14}
              className="animate-spin"
            />
          );
        case "interrupted":
          return (
            <StopCircle
              size={14}
              className="text-orange-500"
            />
          );
        default:
          return (
            <Terminal
              size={14}
              className="text-muted-foreground"
            />
          );
      }
    }, [status]);

    return (
      <div
        className={cn(
          "w-full overflow-hidden rounded-lg border-none shadow-none outline-none transition-colors duration-200 hover:bg-accent",
          isExpanded && hasContent && "bg-accent"
        )}
        style={{ contentVisibility: "auto", containIntrinsicSize: "100px" }}
      >
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleExpanded}
          className={cn(
            "flex w-full items-center justify-between gap-2 border-none px-2 py-2 text-left shadow-none outline-none focus-visible:ring-0 focus-visible:ring-offset-0 disabled:cursor-default"
          )}
          disabled={!hasContent}
        >
          <div className="flex w-full items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              {statusIcon}
              <span className="text-[15px] font-medium tracking-[-0.6px] text-foreground">
                {name}
              </span>
            </div>
            {hasContent &&
              (isExpanded ? (
                <ChevronUp
                  size={14}
                  className="shrink-0 text-muted-foreground"
                />
              ) : (
                <ChevronDown
                  size={14}
                  className="shrink-0 text-muted-foreground"
                />
              ))}
          </div>
        </Button>

        {isExpanded && hasContent && (
          <div className="px-4 pb-4">
            {uiComponent && stream && graphId ? (
              <div className="mt-4">
                <LoadExternalComponent
                  key={uiComponent.id}
                  stream={stream}
                  message={uiComponent}
                  namespace={graphId}
                  meta={{ status, args, result: result ?? "暂无结果" }}
                />
              </div>
            ) : actionRequest && onResume ? (
              // Show tool approval UI when there's an action request but no GenUI
              <div className="mt-4">
                <ToolApprovalInterrupt
                  actionRequest={actionRequest}
                  reviewConfig={reviewConfig}
                  onResume={onResume}
                  isLoading={isResumingInterrupt}
                />
              </div>
            ) : (
              <>
                {argsKeys.length > 0 && (
                  <div className="mt-4">
                    <h4 className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      参数
                    </h4>
                    <div className="space-y-2">
                      {argsEntries.map(([key, value]) => (
                        <ArgItem
                          key={key}
                          argKey={key}
                          value={value}
                          isExpanded={expandedArgs[key]}
                          onToggle={toggleArgExpanded}
                        />
                      ))}
                    </div>
                  </div>
                )}
                {result && (
                  <div className="mt-4">
                    <h4 className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      结果
                    </h4>
                    {name === "export_test_cases_to_excel" &&
                      typeof result === "string" &&
                      result.startsWith("/") && (
                        <div className="mb-2">
                          <Button
                            onClick={() => downloadAgentFile(result)}
                            variant="outline"
                            size="sm"
                            className="gap-1.5"
                          >
                            <Download size={14} />
                            <span>下载 Excel</span>
                          </Button>
                        </div>
                      )}
                    <div className="max-h-96 overflow-y-auto rounded-sm border border-border bg-muted/40">
                      <pre className="m-0 overflow-x-auto whitespace-pre p-2 font-mono text-xs leading-7 text-foreground">
                        {serializedResult}
                      </pre>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    );
  }
);

ToolCallBox.displayName = "ToolCallBox";
// WATERMARK  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlZCTmVnPT06OWI1ODc5MjA=
