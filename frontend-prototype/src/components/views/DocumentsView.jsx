import React, { useState } from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { Badge } from '../common/Badge';
import { 
  FileText, 
  ShieldCheck, 
  Search, 
  CheckCircle2, 
  Sparkles, 
  Tag, 
  Calendar, 
  User, 
  X,
  ExternalLink
} from 'lucide-react';

export const DocumentsView = () => {
  const { state } = useHousehold();
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  const filteredDocs = state.documents.filter((doc) => {
    if (!searchQuery) return true;
    return (
      doc.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.summary.toLowerCase().includes(searchQuery.toLowerCase())
    );
  });

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      {/* Header */}
      <div className="p-6 rounded-3xl bg-gradient-to-r from-emerald-950 via-slate-900 to-indigo-950 border border-emerald-500/30">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="emerald" size="sm">
                <FileText className="w-3.5 h-3.5" />
                Document Agent Knowledge Base
              </Badge>
              <Badge variant="brand" size="sm">Verified RAG Index</Badge>
            </div>
            <h2 className="text-xl lg:text-2xl font-black text-white">
              Verified Documents & Household Ground Truth
            </h2>
            <p className="text-xs text-slate-300 max-w-2xl mt-1 leading-relaxed">
              The Document Agent parses and verifies household documents, extracting structured facts (dietary rules, prescriptions, warranties) to ground multi-agent planning.
            </p>
          </div>

          {/* Search bar */}
          <div className="relative w-full sm:w-64">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search verified documents..."
              className="w-full pl-9 pr-3 py-2 rounded-xl bg-slate-950/80 border border-slate-700 text-xs text-white placeholder-slate-500 outline-none focus:border-emerald-500"
            />
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
          </div>
        </div>
      </div>

      {/* Documents Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filteredDocs.map((doc) => (
          <div
            key={doc.id}
            onClick={() => setSelectedDoc(doc)}
            className="p-5 rounded-3xl bg-slate-900/80 border border-slate-800 hover:border-emerald-500/50 transition-all cursor-pointer group flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between mb-2.5">
                <Badge variant="outline" size="sm" className="font-mono text-[10px]">
                  {doc.id}
                </Badge>
                {doc.verified && (
                  <Badge variant="emerald" size="sm">
                    <ShieldCheck className="w-3 h-3 text-emerald-400" />
                    Verified
                  </Badge>
                )}
              </div>

              <h3 className="text-sm font-bold text-white group-hover:text-emerald-300 transition-colors">
                {doc.title}
              </h3>
              <p className="text-xs text-slate-400 mt-1 line-clamp-2 leading-relaxed">
                {doc.summary}
              </p>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500">
              <span>{doc.verifiedBy}</span>
              <div className="flex gap-1">
                {doc.tags?.slice(0, 2).map((t, idx) => (
                  <span key={idx} className="px-2 py-0.5 rounded-full bg-slate-950 text-slate-400 font-mono text-[10px]">
                    #{t}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Document Inspector Modal */}
      {selectedDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/85 backdrop-blur-md">
          <div className="bg-slate-900 border border-slate-700 rounded-3xl p-6 w-full max-w-xl shadow-2xl animate-scale-up max-h-[85vh] overflow-y-auto space-y-4">
            <div className="flex items-start justify-between gap-3 pb-3 border-b border-slate-800">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant="emerald" size="sm">
                    <ShieldCheck className="w-3 h-3 text-emerald-400" />
                    Verified Household Ground Truth
                  </Badge>
                  <span className="text-xs font-mono text-slate-400">{selectedDoc.id}</span>
                </div>
                <h3 className="text-base font-bold text-white">{selectedDoc.title}</h3>
                <p className="text-xs text-slate-400 mt-0.5">Verified by {selectedDoc.verifiedBy} ({selectedDoc.verificationDate})</p>
              </div>

              <button
                onClick={() => setSelectedDoc(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="p-3.5 rounded-2xl bg-slate-950/80 border border-slate-800">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                  Document Summary
                </span>
                <p className="text-slate-300 leading-relaxed">{selectedDoc.summary}</p>
              </div>

              <div className="p-4 rounded-2xl bg-emerald-950/20 border border-emerald-500/30">
                <div className="flex items-center gap-2 text-emerald-400 font-bold mb-2">
                  <Sparkles className="w-4 h-4" />
                  <span>Document Agent Structured Facts Extraction (RAG)</span>
                </div>
                <pre className="text-emerald-300 font-mono text-xs overflow-x-auto p-2 rounded-xl bg-slate-950/70 border border-emerald-950">
                  {JSON.stringify(selectedDoc.extractedFacts, null, 2)}
                </pre>
              </div>
            </div>

            <div className="flex justify-end pt-3 border-t border-slate-800">
              <button
                onClick={() => setSelectedDoc(null)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
