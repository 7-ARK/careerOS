import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Search, UserCheck, Sparkles, ShieldCheck } from 'lucide-react';

const features = [
  {
    id: 'analysis',
    label: 'Role Analysis',
    icon: <Search className="size-4" />,
    title: 'Understand what they really look for',
    description: 'We instantly parse job descriptions to extract latent requirements. Isolate target experience expectations, prioritize required stacks, and learn company hiring signals.',
    details: [
      'Extracts both hidden soft skills and specific technical tags',
      'Calculates ideal experience-level indicators',
      'Surfaces critical focus keywords directly from postings',
    ],
  },
  {
    id: 'matching',
    label: 'Profile Matching',
    icon: <UserCheck className="size-4" />,
    title: 'Visual match rating benchmarks',
    description: 'Your existing experience matches scored against their requirements. Know precisely which professional achievements to spotlight and where your profile lists skill overlap.',
    details: [
      'Segmented percent match score breakdown',
      'Gap analysis with corrective action recommendations',
      'Candidate strength radar outlining resume leverage points',
    ],
  },
  {
    id: 'drafting',
    label: 'Resume Drafting',
    icon: <Sparkles className="size-4" />,
    title: 'Bespoke resumes, never system-templated',
    description: 'Our backend customizes your resume content for this unique vacancy. Automatically shift emphasis to critical experience nodes, refine action words, and format ATS-friendly layouts.',
    details: [
      'Context-aware bullet rewriting targeting key keywords',
      'Smart section reordering emphasizing relevant skills',
      'Exportable designs built directly to parse perfectly on ATS scanners',
    ],
  },
  {
    id: 'privacy',
    label: 'Private Profiles',
    icon: <ShieldCheck className="size-4" />,
    title: 'Your career evidence stays private',
    description: 'Each account sees only its own candidate profiles, resume inputs, and generated documents. Your profile data is never mixed into another user’s workspace.',
    details: [
      'Email and password protected account access',
      'Candidate profiles isolated by account ownership',
      'Private resume generation and document downloads',
    ],
  },
];

export function Features() {
  const [activeFeature, setActiveFeature] = useState(features[0].id);
  const active = features.find((f) => f.id === activeFeature) || features[0];

  return (
    <section id="features" className="px-6 py-24 md:py-32 bg-card/45 border-t border-b border-border/40 relative">
      <div className="mx-auto max-w-5xl">
        
        {/* Section Header */}
        <div className="mb-16 text-center">
          <span className="mb-3 inline-block text-xs font-semibold uppercase tracking-widest text-[#C9A86A]">
            Capabilities
          </span>
          <h2 className="mx-auto max-w-2xl font-serif text-3xl font-medium tracking-tight text-foreground sm:text-4xl md:text-5xl text-balance">
            Fully featured workflows that accelerate application rates.
          </h2>
        </div>

        {/* Feature Navigation Pill Matrix */}
        <div className="mb-12 flex flex-wrap justify-center gap-2">
          {features.map((feature) => (
            <motion.button
              key={feature.id}
              onClick={() => setActiveFeature(feature.id)}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className={`relative flex items-center justify-center gap-2 whitespace-nowrap rounded-full px-5 py-3 text-sm font-medium transition-all duration-300 cursor-pointer ${
                activeFeature === feature.id
                  ? 'bg-primary text-primary-foreground shadow-lg shadow-primary/10'
                  : 'bg-secondary text-muted-foreground hover:text-foreground hover:bg-border/60'
              }`}
            >
              {feature.icon}
              <span>{feature.label}</span>
            </motion.button>
          ))}
        </div>

        {/* Feature content box */}
        <div className="grid gap-12 lg:grid-cols-2 lg:gap-16 items-center">
          
          {/* Detailed Specifications of selected Feature */}
          <AnimatePresence mode="wait">
            <motion.div
              key={active.id}
              initial={{ opacity: 0, x: -15 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 15 }}
              transition={{ duration: 0.4 }}
            >
              <h3 className="mb-4 font-serif text-2.5xl font-medium text-foreground leading-tight md:text-3xl">
                {active.title}
              </h3>
              <p className="mb-8 text-sm md:text-base text-muted-foreground leading-relaxed">
                {active.description}
              </p>

              <ul className="space-y-4">
                {active.details.map((detail, i) => (
                  <li key={detail} className="flex items-start gap-3 group">
                    <span className="mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/20 text-primary">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="10"
                        height="10"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="3.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    </span>
                    <span className="text-sm text-foreground/90">{detail}</span>
                  </li>
                ))}
              </ul>
            </motion.div>
          </AnimatePresence>

          {/* Interactive Live Screen Sandbox Simulation */}
          <div className="relative">
            <div className="relative overflow-hidden rounded-2xl bg-[#121816]/70 border border-border p-1 shadow-2xl">
              {/* Fake web terminal chrome bar */}
              <div className="flex items-center gap-2 px-4 py-3 border-b border-border/50 bg-[#171F1C]">
                <div className="flex gap-1.5">
                  <div className="h-2.5 w-2.5 rounded-full bg-[#C85A5A]/70" />
                  <div className="h-2.5 w-2.5 rounded-full bg-[#C89B5A]/70" />
                  <div className="h-2.5 w-2.5 rounded-full bg-[#8FAE5D]/70" />
                </div>
                <div className="mx-auto text-[10px] font-mono text-muted-foreground/50 lowercase tracking-widest pl-0 sm:pl-10">
                  sandbox_simulation.js
                </div>
              </div>
              
              {/* Screen representation */}
              <div className="p-6 space-y-4 min-h-[300px] bg-background/40">
                <AnimatePresence mode="wait">
                  {activeFeature === 'analysis' && (
                    <motion.div
                       key="sim-and"
                       initial={{ opacity: 0 }}
                       animate={{ opacity: 1 }}
                       exit={{ opacity: 0 }}
                       className="space-y-3"
                    >
                      <div className="flex items-center gap-3 p-3 rounded-lg bg-secondary/45 border border-border/40">
                        <div className="h-10 w-10 rounded-lg bg-primary/15 flex items-center justify-center">
                          <Search className="size-5 text-primary" />
                        </div>
                        <div className="flex-1">
                          <div className="text-sm font-medium text-foreground">Analyzing posting link...</div>
                          <div className="text-[10px] text-muted-foreground uppercase font-mono">extracted schema metadata</div>
                        </div>
                      </div>
                      <div className="space-y-2 p-3 rounded-lg bg-card/40 border border-border/30">
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-muted-foreground">Extracted Tech Stack</span>
                          <span className="text-[10px] text-brand-amber uppercase font-mono">15 tags isolated</span>
                        </div>
                        <div className="flex flex-wrap gap-1.5 pt-1">
                          {['React 19', 'Next.js 15', 'Tailwind', 'Node/TS', 'Postgres', 'GraphQL', 'AWS Lambdas'].map((skill, index) => {
                            const badgeStyle = index % 3 === 0 
                              ? "bg-primary/10 text-primary border-primary/20" 
                              : index % 3 === 1 
                                ? "bg-brand-amber/10 text-brand-amber border-brand-amber/20" 
                                : "bg-brand-clay/15 text-brand-clay border-brand-clay/20";
                            return (
                              <span key={skill} className={`px-2 py-0.5 text-[10px] rounded border font-mono ${badgeStyle}`}>{skill}</span>
                            );
                          })}
                        </div>
                      </div>
                    </motion.div>
                  )}

                  {activeFeature === 'matching' && (
                    <motion.div
                      key="sim-match"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="space-y-3"
                    >
                      <div className="flex items-center justify-between p-3.5 rounded-lg bg-secondary/40 border border-border/50">
                        <div>
                          <span className="text-xs text-muted-foreground block">Parsed Overlap Metrics</span>
                          <span className="text-sm font-medium text-foreground">Matched Skills</span>
                        </div>
                        <span className="text-2xl font-serif font-bold text-foreground border-b-2 border-primary/50 relative pb-0.5">87% Match</span>
                      </div>
                      <div className="space-y-2.5 px-1">
                        {[
                          { skill: 'React Ecosystem', match: 95 },
                          { skill: 'TypeScript strict typing', match: 90 },
                          { skill: 'System Architecture design', match: 72 },
                        ].map(item => (
                          <div key={item.skill} className="space-y-1">
                            <div className="flex justify-between text-[11px]">
                              <span className="text-muted-foreground">{item.skill}</span>
                              <span className="text-foreground font-mono text-xs flex items-center gap-1">
                                <span className="h-1 w-1 rounded-full bg-brand-amber" />
                                {item.match}%
                              </span>
                            </div>
                            <div className="h-1.5 rounded-full bg-background/80 overflow-hidden relative">
                              <motion.div 
                                initial={{ width: 0 }}
                                animate={{ width: `${item.match}%` }}
                                transition={{ duration: 0.6 }}
                                className="h-full rounded-full bg-primary"
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    </motion.div>
                  )}

                  {activeFeature === 'drafting' && (
                    <motion.div
                      key="sim-draft"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="space-y-3"
                    >
                      <div className="p-3 rounded-lg bg-secondary/40 border border-border/40 space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <div className="w-6 h-6 rounded-full bg-primary/15 flex items-center justify-center">
                              <span className="text-[10px] font-semibold text-primary">JD</span>
                            </div>
                            <div className="text-xs font-medium text-foreground">Acme Senior Frontend Role</div>
                          </div>
                          <span className="text-[9px] font-mono text-muted-foreground uppercase">Format standard</span>
                        </div>
                      </div>
                      <div className="space-y-2 p-3 rounded-lg bg-card/30 border border-border/20">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] uppercase font-mono text-brand-amber font-bold">Bullet rewritten:</span>
                          <motion.span 
                            animate={{ opacity: [0.3, 1, 0.3] }}
                            transition={{ duration: 1.5, repeat: Infinity }}
                            className="w-1.5 h-1.5 rounded-full bg-[#C9A86A]"
                          />
                        </div>
                        <p className="text-[11px] text-foreground/90 italic pl-2.5 border-l border-brand-amber/40 bg-brand-amber/5 py-1 pr-1 rounded-r">
                          "Boosted query latency bounds by 42% utilizing strict PostgreSQL index structures."
                        </p>
                      </div>
                    </motion.div>
                  )}

                  {activeFeature === 'privacy' && (
                    <motion.div
                      key="sim-privacy"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="space-y-3"
                    >
                      <div className="flex items-center gap-3 rounded-lg border border-primary/30 bg-primary/10 p-4">
                        <ShieldCheck className="size-6 text-primary" />
                        <div>
                          <div className="text-sm font-medium text-foreground">Private workspace</div>
                          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Authenticated account</div>
                        </div>
                      </div>
                      {['Candidate profile', 'Tailored resume data', 'Generated documents'].map((item) => (
                        <div key={item} className="flex items-center justify-between rounded-lg border border-border/40 bg-secondary/40 p-3">
                          <span className="text-xs text-foreground">{item}</span>
                          <span className="text-[10px] font-semibold uppercase text-primary">Owner only</span>
                        </div>
                      ))}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          </div>

        </div>
      </div>
    </section>
  );
}
