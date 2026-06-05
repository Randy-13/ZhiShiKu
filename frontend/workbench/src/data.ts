import {
  BookOpenCheck,
  BrainCircuit,
  ClipboardList,
  Database,
  FileInput,
  Layers3,
  ListChecks,
  PenLine,
  Settings,
  Split,
} from "lucide-react";
import type {
  KnowledgeCard,
  MaterialPack,
  MaterialType,
  PerspectiveInsight,
  ProcessingQueueItem,
  ProcessingTask,
  DraftReviewItem,
  DraftVariant,
  InsightCandidate,
  StageNavItem,
} from "./domain";

export const stages: StageNavItem[] = [
  {
    id: "overview",
    label: "Overview",
    description: "End-to-end research production loop",
    icon: ClipboardList,
    count: 6,
    nextId: "inbox",
  },
  {
    id: "inbox",
    label: "Inbox",
    description: "Collect text, screenshots, documents, media, and links",
    icon: FileInput,
    count: 18,
    nextId: "packs",
  },
  {
    id: "packs",
    label: "Material Packs",
    description: "Bundle related materials into one research task",
    icon: Layers3,
    count: 6,
    nextId: "processing",
  },
  {
    id: "processing",
    label: "Processing",
    description: "Parse, split, and extract reusable cards",
    icon: BrainCircuit,
    count: 11,
    nextId: "perspectives",
  },
  {
    id: "perspectives",
    label: "Perspective Mining",
    description: "Read the same material through different roles",
    icon: Split,
    count: 8,
    nextId: "library",
  },
  {
    id: "library",
    label: "Knowledge Library",
    description: "Store evidence, insights, questions, and reusable knowledge",
    icon: Database,
    count: 124,
    nextId: "creation",
  },
  {
    id: "creation",
    label: "Creation Studio",
    description: "Turn knowledge into topics, drafts, and publishing assets",
    icon: PenLine,
    count: 4,
    nextId: "review",
  },
  {
    id: "review",
    label: "Review",
    description: "Audit AI suggestions, draft readiness, and activity history before publishing",
    icon: ListChecks,
    count: 9,
  },
  {
    id: "settings",
    label: "Settings",
    description: "Configure identity, model routing, prompts, standards, and review rules",
    icon: Settings,
    count: 5,
  },
];

export const materialTypes: MaterialType[] = ["Text", "Screenshot", "Document", "Audio/Video", "Link"];

export const workPacks: MaterialPack[] = [
  {
    title: "AI Compute Picks-and-Shovels",
    status: "Processing",
    materials: "12 materials",
    signal: "HBM supply, foundry orders, edge compute",
    progress: 68,
    nextStageId: "processing",
    nextAction: "Continue processing",
  },
  {
    title: "Autonomous Driving Scale-Up",
    status: "Ready for Mining",
    materials: "9 materials",
    signal: "Regulatory inflection, Robotaxi cost curve, vehicle models",
    progress: 42,
    nextStageId: "perspectives",
    nextAction: "Mine perspectives",
  },
  {
    title: "AIPC Supply Chain Orders",
    status: "Ready to Write",
    materials: "7 materials",
    signal: "OEMs, replacement cycle, on-device AI applications",
    progress: 86,
    nextStageId: "creation",
    nextAction: "Start writing",
  },
];

export const knowledgeCards: KnowledgeCard[] = [
  {
    type: "Insight",
    title: "The value of picks-and-shovels stocks comes from bottleneck migration, not concept hype.",
    source: "Linked to 4 evidence cards",
    confidence: "High",
  },
  {
    type: "Evidence",
    title: "HBM capacity expansion is slower than volatility on the GPU demand side.",
    source: "Earnings, industry interviews, broker notes",
    confidence: "Medium High",
  },
  {
    type: "Question",
    title: "Will edge compute weaken the durability of cloud capex?",
    source: "Needs counter-evidence",
    confidence: "Needs Review",
  },
];

export const perspectives: PerspectiveInsight[] = [
  { role: "Writer", insight: "Find narrative tension between decade-long bets and sudden market payoff." },
  { role: "Investor", insight: "Separate demand certainty, supply bottlenecks, and valuation realization." },
  { role: "Retail Trader", insight: "Avoid treating an industry trend as proof that every ticker will rise." },
  { role: "Institution", insight: "Watch order visibility, margin trend, and capex rhythm." },
  { role: "Founder", insight: "Look for gaps in tooling, data processing, and vertical applications." },
  { role: "Researcher", insight: "Separate facts, inference, sentiment, and falsifiable hypotheses first." },
];

export const insightCandidates: InsightCandidate[] = [
  {
    role: "Writer",
    claim: "The strongest article angle is the tension between a quiet decade-long bet and sudden market recognition.",
    evidence: "The selected pack links supply bottlenecks with order visibility and market narrative shifts.",
    counterpoint: "The story can become too heroic unless it includes execution risk and valuation discipline.",
  },
  {
    role: "Investor",
    claim: "The investable question is whether the bottleneck migrates from GPU demand to memory and packaging supply.",
    evidence: "Evidence cards point to slower HBM capacity expansion and stronger demand-side volatility.",
    counterpoint: "If capex normalizes faster than expected, the bottleneck premium can compress quickly.",
  },
  {
    role: "Retail Trader",
    claim: "The main user risk is confusing a real industry trend with a blanket buy signal across all tickers.",
    evidence: "Prior material shows concept names often rise before earnings visibility catches up.",
    counterpoint: "Momentum can still dominate short windows, so timing language must stay careful.",
  },
  {
    role: "Institution",
    claim: "The institutional lens should prioritize order visibility, margin direction, and capex rhythm.",
    evidence: "The pack contains earnings notes, broker summaries, and supply-chain order commentary.",
    counterpoint: "The current evidence set still needs more primary-source confirmation.",
  },
  {
    role: "Founder",
    claim: "The opportunity space may sit in tooling around data processing, vertical workflows, and deployment support.",
    evidence: "Several notes mention workflow gaps around AI infrastructure adoption.",
    counterpoint: "A founder lens can over-read market pain unless paired with customer evidence.",
  },
  {
    role: "Researcher",
    claim: "The first research task is separating fact, inference, market sentiment, and falsifiable hypotheses.",
    evidence: "The material pack mixes raw reports, interpretation, and market commentary.",
    counterpoint: "Over-structuring too early can slow down useful creative synthesis.",
  },
];

export const processingTasks: ProcessingTask[] = [
  { title: "Format Parsing", body: "Detect type, extract text, run OCR, transcribe audio and video." },
  { title: "Knowledge Splitting", body: "Split by topic, person, company, industry, viewpoint, data, and event." },
  { title: "Card Extraction", body: "Create summary, knowledge, insight, evidence, and question cards." },
];

export const creationSteps = [
  "Select knowledge materials",
  "Generate topics",
  "Generate article",
  "Revise article",
  "Select images",
  "Format layout",
  "Pre-publish check",
  "Publish draft",
];

export const processingQueue: ProcessingQueueItem[] = [
  {
    title: "Parse original materials",
    status: "Ready",
    output: "Clean text, OCR notes, transcript fragments",
  },
  {
    title: "Split by research units",
    status: "Running",
    output: "Company, industry, data point, event, claim",
  },
  {
    title: "Extract candidate cards",
    status: "Review",
    output: "Summary, insight, evidence, and question cards",
  },
];

export const draftReviews: DraftReviewItem[] = [
  {
    title: "Topic angle",
    status: "Ready",
    detail: "Why picks-and-shovels names may outperform pure concept trades.",
  },
  {
    title: "Evidence coverage",
    status: "Needs edit",
    detail: "Add one counterexample before generating the full article.",
  },
  {
    title: "Publishing fit",
    status: "Ready",
    detail: "Long-form article can be adapted into image post and short script.",
  },
];

export const libraryStats = [
  ["Summary Cards", "32"],
  ["Insight Cards", "41"],
  ["Evidence Cards", "76"],
  ["Question Cards", "18"],
];

export const creationChannels = [
  "WeChat long-form",
  "Xiaohongshu image post",
  "Short video script",
  "Long video outline",
] as const;

export const draftVariants: DraftVariant[] = [
  {
    channel: "WeChat long-form",
    title: "Why AI picks-and-shovels names may still matter after the hype",
    structure: ["Opening tension", "Industry bottleneck", "Evidence chain", "Counterpoint", "Investment takeaway"],
    checklist: ["Evidence cited", "Counterargument included", "Headline clear", "Publication-ready layout"],
  },
  {
    channel: "Xiaohongshu image post",
    title: "AI infrastructure: 5 signals hidden in the supply chain",
    structure: ["Cover hook", "Signal cards", "Risk reminder", "Final summary"],
    checklist: ["Cover title under control", "Card copy concise", "Visual rhythm checked", "No unsupported claim"],
  },
  {
    channel: "Short video script",
    title: "The real AI bottleneck may not be where most traders look",
    structure: ["3-second hook", "One clear chart", "Main claim", "Risk caveat", "Call to review sources"],
    checklist: ["Hook direct", "Script under 60 seconds", "One idea only", "Evidence easy to narrate"],
  },
  {
    channel: "Long video outline",
    title: "From GPU demand to HBM supply: mapping the AI infrastructure chain",
    structure: ["Intro", "Timeline", "Supply chain map", "Case studies", "Open questions", "Closing view"],
    checklist: ["Chapter logic clear", "Evidence grouped", "Visual aids planned", "Open questions retained"],
  },
];

export { BookOpenCheck };
