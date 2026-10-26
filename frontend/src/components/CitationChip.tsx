import React from "react";
import { BookOpen } from "lucide-react";

interface CitationChipProps {
  id: string; // e.g. "S1"
  onClick: (sourceId: string) => void;
}

export const CitationChip: React.FC<CitationChipProps> = ({ id, onClick }) => {
  return (
    <button
      type="button"
      className="citation-chip"
      onClick={(e) => {
        e.stopPropagation();
        onClick(id);
      }}
      title={`View source ${id}`}
      aria-label={`View source citation ${id}`}
    >
      <BookOpen size={11} />
      <span>{id}</span>
    </button>
  );
};
