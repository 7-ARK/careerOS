import { useRef, useState, useEffect, ReactNode } from 'react';
import { motion, useScroll, useTransform } from 'motion/react';
import { Link2, Sparkles, CheckCircle2, FileDown, Layers, Search, UserCheck } from 'lucide-react';

const steps = [
  {
    id: 1,
    title: 'Drop a job link',
    description: 'Paste any job posting URL to fetch structural requirements',
    icon: <Link2 className="size-4" />,
  },
  {
    id: 2,
    title: 'Role analysis',
    description: 'Our system extracts core soft skills, tech stacks, and culture cues',
    icon: <Search className="size-4" />,
  },
  {
    id: 3,
    title: 'Profile match',
    description: 'Evaluate your experiences and isolate key matching strengths',
    icon: <UserCheck className="size-4" />,
  },
  {
    id: 4,
    title: 'Resume tailored',
    description: 'Direct context-aware bullet rewriting optimized for ATS systems',
    icon: <Sparkles className="size-4" />,
  },
  {
    id: 5,
    title: 'Export and saved',
    description: 'Sleek, compliant PDF finalized and filed in your dashboard',
    icon: <FileDown className="size-4" />,
  },
];

export function FolderJourney() {
  const containerRef = useRef<HTMLDivElement>(null);
  
  // Track continuous scroll progress inside this sticky container
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ['start start', 'end end'],
  });

  const [windowWidth, setWindowWidth] = useState(1200);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const handleResize = () => setWindowWidth(window.innerWidth);
      handleResize();
      window.addEventListener('resize', handleResize);
      return () => window.removeEventListener('resize', handleResize);
    }
  }, []);

  const isDesktop = windowWidth >= 1024;
  const isTablet = windowWidth >= 768 && windowWidth < 1024;

  const folderYMultiplier = isDesktop ? 1.0 : isTablet ? 0.7 : 0.35;
  const resumeMultiplier = isDesktop ? 1.0 : isTablet ? 0.78 : 0.52;
  const scanBarMultiplier = isDesktop ? 1.0 : isTablet ? 0.78 : 0.52;

  // FOLDER POSITIONING: Start very high up, travel down, and slide deep down into the pipeline deck at the end
  const baseFolderY = useTransform(scrollYProgress, 
    [0, 0.2, 0.4, 0.6, 0.8, 0.9, 1.0], 
    [-340, -180, -20, 80, 160, 220, 480]
  );
  const folderY = useTransform(baseFolderY, (y) => y * folderYMultiplier);
  
  // Scale goes up to make the folder massive and majestic, then scales down slightly of entering dock
  const folderScale = useTransform(scrollYProgress, [0, 0.2, 0.8, 0.9, 1.0], [0.95, 1.08, 1.08, 1.0, 0.92]);

  // Make opacity fade slightly as it sinks into the pipeline tray at the final output
  const folderOpacity = useTransform(scrollYProgress, [0, 0.85, 0.95, 1.0], [1.0, 1.0, 0.92, 0.65]);

  // Folder flap rotation (stays closed on step 1, flips fully open for details, then locks sealed at step 5)
  const folderFlapRotate = useTransform(scrollYProgress, [0, 0.15, 0.28, 0.80, 0.90], [0, -45, -115, -115, 0]);

  // Resume paper slides up from folder core, stands tall, then gracefully slides back down inside when archived
  const baseResumeY = useTransform(scrollYProgress, [0.15, 0.35, 0.75, 0.80, 0.92], [280, 0, -30, 120, 280]);
  const resumeY = useTransform(baseResumeY, (y) => y * resumeMultiplier);
  const resumeOpacity = useTransform(scrollYProgress, [0.15, 0.28, 0.80, 0.90], [0, 1, 1, 0]);
  const resumeScale = useTransform(scrollYProgress, [0.15, 0.4, 0.75, 0.80, 0.92], [0.8, 1.0, 1.03, 0.9, 0.8]);

  // Scanning indicator glow during Role Analysis (Step 2)
  const baseScanBarY = useTransform(scrollYProgress, [0.22, 0.38], [-30, 240]);
  const scanBarY = useTransform(baseScanBarY, (y) => y * scanBarMultiplier);
  const scanBarOpacity = useTransform(scrollYProgress, [0.20, 0.22, 0.38, 0.40], [0, 1, 1, 0]);

  // Matching Score Radial Animation during Profile Match (Step 3)
  const matchRingOpacity = useTransform(scrollYProgress, [0.40, 0.42, 0.58, 0.60], [0, 1, 1, 0]);
  const matchScoreValue = useTransform(scrollYProgress, [0.4, 0.52], [42, 94]);

  // Interactive Tailoring highlight during Resume Tailoring (Step 4)
  const rewriteHighlightOpacity = useTransform(scrollYProgress, [0.60, 0.62, 0.78, 0.80], [0, 1, 1, 0]);
  const tailorStampedScale = useTransform(scrollYProgress, [0.68, 0.74], [2.5, 1.0]);
  const tailorStampedOpacity = useTransform(scrollYProgress, [0.68, 0.72, 0.78, 0.80], [0, 1, 1, 0]);

  // Active step highlighter
  const activeStep = useTransform(scrollYProgress, 
    [0.1, 0.3, 0.5, 0.7, 0.9], 
    [0, 1, 2, 3, 4]
  );

  return (
    <section 
      id="how-it-works" 
      ref={containerRef}
      className="relative min-h-[300vh] bg-background py-12 md:py-0"
    >
      {/* Sticky layout framing */}
      <div className="sticky top-0 h-screen overflow-hidden flex flex-col justify-center bg-background z-10">
        
        {/* Subtle background deck line mimicking a shelf */}
        <div className="absolute bottom-[20%] left-0 right-0 h-px bg-gradient-to-r from-transparent via-border/50 to-transparent pointer-events-none" />
 
        <div className="mx-auto w-full max-w-6xl px-6 md:px-8 py-4">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6 md:gap-12 xl:gap-16 items-center">
            
            {/* Folder Animation on Left (7 of 12 columns - MAJESTIC & PROMINENT) */}
            <div className="col-span-12 md:col-span-6 lg:col-span-7 flex justify-center items-center order-2 md:order-1 select-none pr-0 md:pr-4 lg:pr-8">
              
              <motion.div 
                style={{ y: folderY, scale: folderScale, opacity: folderOpacity }}
                className="relative w-full max-w-[260px] sm:max-w-[340px] md:max-w-[420px] lg:max-w-[500px] aspect-[4/3] origin-bottom transition-all duration-300"
              >
                {/* Visual Anchor Desk/Drawer representation where the folder stays inside and archives */}
                <div className="absolute -bottom-16 left-[5%] right-[5%] h-12 bg-gradient-to-b from-[#17201C] to-[#0D1110] rounded-3xl border border-border/30 opacity-70 blur-[2px] -z-20 shadow-2xl" />

                <div className="relative" style={{ perspective: '1200px' }}>
                  
                  {/* Folder Backing Panel */}
                  <div className="relative w-full aspect-[4/3]">
                    
                    {/* Retro filing folder tab */}
                    <div className="absolute -top-[14px] left-8 w-24 h-[16px] bg-[#1E2723] rounded-t-lg shadow-[inset_0_-2px_6px_rgba(0,0,0,0.4)] border-t border-r border-[#2A322E]/80" />
                    
                    {/* Majestic background gradient safe */}
                    <div className="absolute inset-0 bg-gradient-to-b from-[#25302B] to-[#121816] rounded-2xl shadow-[inset_0_2px_4px_rgba(255,255,255,0.05),_0_25px_50px_-12px_rgba(0,0,0,0.8)] border border-[#2A322E]/80 -z-10" />
                    
                    {/* CUSTOM ACTIVE RESUME SHEET CONTAINER */}
                    <motion.div
                      style={{ y: resumeY, opacity: resumeOpacity, scale: resumeScale }}
                      className="absolute left-[7%] right-[7%] top-[10px] h-[112%] origin-bottom"
                    >
                      <div className="w-full h-full bg-[#F2F1EC] rounded-lg shadow-2xl overflow-hidden border border-[#A9AAA3]/30 text-[#0D1110] flex flex-col justify-between p-5 relative">
                        
                        {/* High-tech scanner laser line overlay (Step 2 Only) */}
                        <motion.div 
                          style={{ y: scanBarY, opacity: scanBarOpacity }}
                          className="absolute left-0 right-0 h-1 bg-gradient-to-r from-transparent via-[#93A86B] to-transparent shadow-[0_0_12px_#93A86B] pointer-events-none z-30"
                        />

                        {/* Matching score ring overlay (Step 3 Only - sophisticated Amber highlighting!) */}
                        <motion.div
                          style={{ opacity: matchRingOpacity }}
                          className="absolute inset-0 bg-[#F2F1EC]/95 flex flex-col items-center justify-center gap-3 z-20"
                        >
                          <div className="relative flex items-center justify-center w-28 h-28">
                            <svg className="w-full h-full transform -rotate-90">
                              <circle cx="56" cy="56" r="44" stroke="#E1DFD5" strokeWidth="6" fill="transparent" />
                              <motion.circle 
                                cx="56" cy="56" r="44" stroke="#C9A86A" strokeWidth="8" fill="transparent"
                                strokeDasharray={276}
                                strokeDashoffset={72} /* Roughly corresponds to 74% */
                                transition={{ duration: 1 }}
                              />
                            </svg>
                            <span className="absolute text-2xl font-serif font-semibold text-[#0D1110]">94%</span>
                          </div>
                          <div className="text-center">
                            <span className="text-xs font-serif italic text-brand-amber font-semibold uppercase tracking-wider block">Profile Score: Exceptional</span>
                            <span className="text-[10px] text-muted-foreground block mt-1">Excellent requirement overlap identified</span>
                          </div>
                        </motion.div>

                        {/* Document Content */}
                        <div className="space-y-4">
                          {/* Document Header */}
                          <div className="border-b border-[#D1CEC2] pb-3">
                            <div className="flex items-center justify-between">
                              <div>
                                <h4 className="text-sm font-bold tracking-tight text-[#0D1110] font-sans">JANE DOE</h4>
                                <p className="text-[10px] text-muted-foreground font-mono">Senior Engineer | Seattle, WA</p>
                              </div>
                              <div className="h-6 w-14 bg-[#0D1110]/5 border border-[#0D1110]/10 rounded flex items-center justify-center text-[8px] font-mono font-bold text-[#0D1110]">
                                Page 1 of 1
                              </div>
                            </div>
                          </div>
                          
                          {/* Main Bullet Points */}
                          <div className="space-y-2.5 text-[9px] md:text-xs">
                            <div className="space-y-1">
                              {/* Job requirement reference list */}
                              <div className="flex justify-between items-center">
                                <span className="font-semibold text-[10px] tracking-wide uppercase font-sans">Professional Experience</span>
                                <motion.span 
                                  className="text-[9px] text-[#93A86B] font-medium font-mono animate-pulse"
                                  animate={{ opacity: [1, 0.4, 1] }}
                                  transition={{ duration: 2, repeat: Infinity }}
                                >
                                  ■ Processing tailoring
                                </motion.span>
                              </div>
                              
                              <p className="text-muted-foreground italic text-[9px]">Acme Software Platform — Lead Developer</p>
                            </div>
                            
                            <div className="space-y-2">
                              {/* Standard text elements (glowing or normal) */}
                              <div className="relative">
                                <motion.p 
                                  className="text-muted-foreground leading-relaxed pl-3 font-sans"
                                  style={{ color: useTransform(scrollYProgress, [0.65, 0.85], ['#555C57', '#0D1110']) }}
                                >
                                  • Architected cloud pipeline handling 12k concurrent requests using Node.js and TypeScript.
                                </motion.p>
                                
                                <motion.div 
                                  style={{ opacity: rewriteHighlightOpacity }}
                                  className="absolute inset-0 bg-[#C9A86A]/8 border-l-2 border-[#C9A86A] -mx-1"
                                />
                              </div>

                              <div className="relative">
                                <motion.p 
                                  className="text-muted-foreground leading-relaxed pl-3"
                                  style={{ color: useTransform(scrollYProgress, [0.65, 0.85], ['#555C57', '#0D1110']) }}
                                >
                                  • Direct optimization of database query speeds by <span className="font-semibold text-[#93A86B]">42%</span> using PostgreSQL indexed triggers.
                                </motion.p>
                                <motion.div 
                                  style={{ opacity: rewriteHighlightOpacity }}
                                  className="absolute inset-0 bg-[#93A86B]/8 border-l-2 border-[#93A86B] -mx-1"
                                />
                              </div>

                              <p className="text-muted-foreground leading-relaxed pl-3">• Supervised cross-functional team of 6 engineers launching cloud infrastructure integrations.</p>
                            </div>
                          </div>
                        </div>

                        {/* Stamp overlaying the document */}
                        <motion.div
                          style={{ scale: tailorStampedScale, opacity: tailorStampedOpacity }}
                          className="absolute right-6 bottom-16 border-2 border-dashed border-[#A87962] text-[#A87962] text-[10px] font-bold uppercase tracking-wider px-3 py-1.5 rounded -rotate-12 z-10 shadow-lg bg-[#F2F1EC]"
                        >
                          ATS-Tailored Ready
                        </motion.div>

                        <div className="flex justify-between items-center border-t border-[#D1CEC2] pt-2.5 mt-auto">
                          <span className="text-[9px] font-mono text-muted-foreground uppercase">Format: standard-PDF</span>
                          
                          {/* Interacting button triggers download if user is at the end */}
                          <motion.button 
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                            className="bg-[#0D1110] text-[#F2F1EC] text-[9px] font-semibold tracking-tight px-3 py-1.5 rounded-full shadow border border-border/20 flex items-center gap-1.5"
                          >
                            <FileDown className="size-3 text-[#93A86B]" />
                            <span>Export Draft</span>
                          </motion.button>
                        </div>
                      </div>
                    </motion.div>

                    {/* FRONT OVERLAPPING FOLDER FLAP PANEL */}
                    <motion.div 
                      className="absolute inset-0 bg-gradient-to-b from-[#4F5B53] to-[#121816] rounded-2xl origin-bottom shadow-[inset_0_1px_0_rgba(255,255,255,0.08),_0_5px_15px_rgba(0,0,0,0.5)] border border-[#2A322E]/80 select-none z-10 cursor-pointer"
                      style={{ 
                        rotateX: folderFlapRotate,
                        transformStyle: 'preserve-3d',
                      }}
                    >
                      {/* Folder Title Emblem */}
                      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-[#121816]/95 border border-[#2A322E] px-5 py-2 rounded-xl text-xs font-mono font-semibold tracking-tight text-foreground shadow-2xl flex items-center gap-2">
                        <Layers className="size-3.5 text-brand-amber" />
                        <span>careerOS_workspace</span>
                      </div>
                    </motion.div>
                  </div>
                </div>
              </motion.div>
            </div>

            {/* Scrolling Instructions on Right (5 of 12 columns) */}
            <div className="col-span-12 md:col-span-6 lg:col-span-5 pt-4 md:pt-0 order-1 md:order-2 flex flex-col justify-center">
              
              {/* Section Header */}
              <div className="mb-4 md:mb-5 text-left py-1">
                <span className="mb-1 md:mb-2 inline-block text-xs font-semibold uppercase tracking-widest text-brand-amber">
                  The Engine
                </span>
                <h2 className="font-serif text-xl sm:text-2xl md:text-3.5xl lg:text-4xl font-medium tracking-tight text-foreground text-balance leading-normal lg:leading-snug">
                  From cold job link to tailored success.
                </h2>
              </div>

              {/* Connecting vertical timeline of checklist */}
              <div className="relative">
                <div className="absolute left-4 md:left-5 top-5 bottom-5 w-px bg-gradient-to-b from-primary/30 via-border to-border/10" />
                
                <div className="space-y-1">
                  {steps.map((step, index) => (
                    <StepItem 
                      key={step.id} 
                      step={step} 
                      index={index}
                      activeStep={activeStep}
                    />
                  ))}
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>
    </section>
  );
}

interface StepItemProps {
  key?: any;
  step: {
    id: number;
    title: string;
    description: string;
    icon: ReactNode;
  };
  index: number;
  activeStep: any;
}

function StepItem({ 
  step, 
  index, 
  activeStep 
}: StepItemProps) {
  // Use scroll transforms to calculate if this step is actively selected
  const isActive = useTransform(activeStep, (v: any) => Math.round(v as number) === index);

  return (
    <motion.div
      initial={{ opacity: 0.45 }}
      style={{
        opacity: useTransform(isActive, (v) => v ? 1.0 : 0.42),
      }}
      className="group relative flex items-start gap-3 md:gap-4 py-1.5 md:py-2"
    >
      {/* Visual step node */}
      <motion.div
        className="relative z-10 flex h-8 w-8 md:h-10 md:w-10 shrink-0 items-center justify-center rounded-xl transition-all duration-300"
        style={{
          backgroundColor: useTransform(isActive, (v) => v ? '#93A86B' : '#171F1C'),
          color: useTransform(isActive, (v) => v ? '#101210' : '#A9AAA3'),
          borderColor: useTransform(isActive, (v) => v ? 'rgba(201, 168, 106, 0.3)' : 'transparent'),
          boxShadow: useTransform(isActive, (v) => v ? '0 4px 12px rgba(147, 168, 107, 0.25)' : 'none'),
        }}
      >
        {step.icon}
        
        {/* Pulse beacon on the active node */}
        <motion.div
          className="absolute inset-0 rounded-xl bg-brand-amber"
          style={{
            opacity: useTransform(isActive, (v) => v ? 0.2 : 0),
            scale: useTransform(isActive, (v) => v ? 1.4 : 1.0),
          }}
          transition={{ duration: 0.4 }}
        />
      </motion.div>

      {/* Text block */}
      <div>
        <motion.h3 
          className="text-sm md:text-base font-sans font-medium transition-colors"
          style={{
            color: useTransform(isActive, (v) => v ? '#F2F1EC' : '#A9AAA3'),
          }}
        >
          {step.title}
        </motion.h3>
        <motion.p 
          className="mt-0.5 text-[11px] md:text-xs transition-colors"
          style={{
            color: useTransform(isActive, (v) => v ? '#FFFFFF' : '#A9AAA3'),
          }}
        >
          {step.description}
        </motion.p>
      </div>
    </motion.div>
  );
}
