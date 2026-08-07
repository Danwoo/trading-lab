// components/shared/ui/MarkdownRenderer.tsx
"use client";

import React, { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import type { Components } from "react-markdown";

interface Props {
  content: string;
  className?: string;
}

const components: Components = {
  // 코드 블록 / 인라인 코드
  code({ className, children, ...props }) {
    const match = /language-(\w+)/.exec(className || "");
    const isBlock = String(children).includes("\n");

    if (isBlock || match) {
      return (
        <div className="relative my-2">
          {match && (
            <div className="absolute top-0 right-0 px-2 py-0.5 text-[10px] text-gray-400 bg-gray-700 rounded-bl rounded-tr-md select-none">
              {match[1]}
            </div>
          )}
          <pre className="bg-gray-800 text-gray-100 rounded-md p-3 overflow-x-auto text-sm leading-relaxed">
            <code className={className} {...props}>
              {children}
            </code>
          </pre>
        </div>
      );
    }

    return (
      <code className="bg-gray-200 text-red-600 px-1.5 py-0.5 rounded text-sm font-mono" {...props}>
        {children}
      </code>
    );
  },
  // 표
  table({ children }) {
    return (
      <div className="overflow-x-auto my-2">
        <table className="min-w-full border-collapse border border-gray-300 text-sm">{children}</table>
      </div>
    );
  },
  thead({ children }) {
    return <thead className="bg-gray-100">{children}</thead>;
  },
  th({ children }) {
    return <th className="border border-gray-300 px-3 py-1.5 text-left font-semibold">{children}</th>;
  },
  td({ children }) {
    return <td className="border border-gray-300 px-3 py-1.5">{children}</td>;
  },
  // 목록
  ul({ children }) {
    return <ul className="list-disc list-inside my-1 space-y-0.5">{children}</ul>;
  },
  ol({ children }) {
    return <ol className="list-decimal list-inside my-1 space-y-0.5">{children}</ol>;
  },
  li({ children }) {
    return <li className="leading-relaxed">{children}</li>;
  },
  // 제목
  h1({ children }) {
    return <h1 className="text-xl font-bold mt-3 mb-1">{children}</h1>;
  },
  h2({ children }) {
    return <h2 className="text-lg font-bold mt-3 mb-1">{children}</h2>;
  },
  h3({ children }) {
    return <h3 className="text-base font-semibold mt-2 mb-1">{children}</h3>;
  },
  // 단락
  p({ children }) {
    return <p className="my-1 leading-relaxed">{children}</p>;
  },
  // 인용
  blockquote({ children }) {
    return <blockquote className="border-l-4 border-gray-300 pl-3 my-2 text-gray-600 italic">{children}</blockquote>;
  },
  // 링크
  a({ href, children }) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
        {children}
      </a>
    );
  },
  // 수평선
  hr() {
    return <hr className="my-3 border-gray-300" />;
  },
  // 강조
  strong({ children }) {
    return <strong className="font-semibold">{children}</strong>;
  },
};

function MarkdownRendererInner({ content, className = "" }: Props) {
  if (!content) return null;

  return (
    <div className={`markdown-body text-sm leading-relaxed ${className}`}>
      <ReactMarkdown
        remarkPlugins={[[remarkGfm, { singleTilde: false }], remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

export const MarkdownRenderer = memo(MarkdownRendererInner);
