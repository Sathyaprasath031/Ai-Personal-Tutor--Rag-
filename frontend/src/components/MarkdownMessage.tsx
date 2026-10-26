import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { CitationChip } from "./CitationChip";

interface MarkdownMessageProps {
  content: string;
  onCitationClick: (sourceId: string) => void;
}

export const MarkdownMessage: React.FC<MarkdownMessageProps> = ({ content, onCitationClick }) => {
  // Custom text node processor that converts [S1], [S2] into interactive CitationChips
  const renderTextWithCitations = (text: string) => {
    const parts = text.split(/(\[S\d+\])/g);
    return parts.map((part, index) => {
      const match = part.match(/^\[(S\d+)\]$/);
      if (match) {
        return (
          <CitationChip
            key={index}
            id={match[1]}
            onClick={onCitationClick}
          />
        );
      }
      return part;
    });
  };

  const components = useMemo(
    () => ({
      p: ({ children }: any) => {
        return (
          <p>
            {React.Children.map(children, (child) => {
              if (typeof child === "string") {
                return renderTextWithCitations(child);
              }
              return child;
            })}
          </p>
        );
      },
      li: ({ children }: any) => {
        return (
          <li>
            {React.Children.map(children, (child) => {
              if (typeof child === "string") {
                return renderTextWithCitations(child);
              }
              return child;
            })}
          </li>
        );
      },
      // Ensure raw code blocks are highlighted cleanly
      code: ({ node, inline, className, children, ...props }: any) => {
        return (
          <code className={className} {...props}>
            {children}
          </code>
        );
      },
    }),
    [onCitationClick]
  );

  return (
    <div className="markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};
