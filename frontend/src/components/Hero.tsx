import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { ArrowRight } from 'lucide-react';

const words = ['every job', 'each role', 'new postings', 'applications'];

export function Hero() {
  const [wordIndex, setWordIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setWordIndex((prev) => (prev + 1) % words.length);
    }, 2800);
    return () => clearInterval(interval);
  }, []);

  return (
    <section className="relative min-h-[100vh] flex items-center justify-center overflow-hidden px-6 pt-32 pb-20 bg-background text-foreground" id="hero-section">
      {/* Subtle grain texture */}
      <div className="pointer-events-none absolute inset-0 opacity-[0.02]" style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`
      }} />
      
      {/* Animated background glow - Highly dampened to prevent green-only oversaturation */}
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <motion.div
          animate={{
            scale: [1, 1.1, 1],
            opacity: [0.03, 0.07, 0.03],
          }}
          transition={{ duration: 12, repeat: Infinity, ease: 'easeInOut' }}
          className="absolute top-1/4 left-1/2 -translate-x-1/2 h-[550px] w-[550px] rounded-full bg-primary/20 blur-[130px]"
        />
        <motion.div
          animate={{
            scale: [1.1, 1, 1.1],
            opacity: [0.02, 0.06, 0.02],
          }}
          transition={{ duration: 14, repeat: Infinity, ease: 'easeInOut', delay: 2 }}
          className="absolute bottom-1/3 right-1/4 h-[400px] w-[400px] rounded-full bg-brand-amber/15 blur-[110px]"
        />
      </div>

      <div className="mx-auto max-w-4xl text-center pb-8">
        {/* Main headline */}
        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1.0, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="mb-8 font-serif text-4xl font-medium leading-[1.2] tracking-tight text-foreground sm:text-5xl md:text-6xl lg:text-7xl flex flex-col items-center justify-center gap-1 sm:gap-2"
        >
          <span className="text-balance block">
            Stop rebuilding your resume for
          </span>
          <span className="relative block h-[1.2em] w-full text-center">
            <AnimatePresence mode="wait">
              <motion.span
                key={wordIndex}
                initial={{ opacity: 0, y: 15, filter: 'blur(4px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, y: -15, filter: 'blur(4px)' }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
                className="absolute left-0 right-0 text-brand-amber border-b border-brand-amber/25 pb-1 inline-block w-fit mx-auto"
              >
                {words[wordIndex]}
              </motion.span>
            </AnimatePresence>
          </span>
        </motion.h1>

        {/* Subheadline */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.3 }}
          className="mx-auto mb-12 max-w-xl text-balance text-base text-muted-foreground sm:text-lg leading-relaxed"
        >
          Paste any job posting link. We instantly analyze the underlying requirements, 
          evaluate where you stand, and craft a tailored resume optimized for their system.
        </motion.p>

        {/* CTA section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.4 }}
          className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center"
        >
          <motion.a
            href="#analyze-job"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="group relative overflow-hidden rounded-full bg-primary px-8 py-4 text-base font-medium text-primary-foreground transition-all duration-300 shadow-md shadow-primary/10 hover:shadow-primary/25"
          >
            <span className="relative z-10 flex items-center gap-2">
              Start building
              <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" />
            </span>
          </motion.a>
          
          <motion.a
            href="#features"
            whileHover={{ scale: 1.02 }}
            className="flex items-center gap-2 rounded-full border border-border bg-transparent px-6 py-4 text-base text-muted-foreground transition-all hover:border-brand-amber/50 hover:bg-brand-amber/5 hover:text-foreground"
          >
            Explore features
          </motion.a>
        </motion.div>
      </div>

      {/* Scroll indicator */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.8 }}
        className="absolute bottom-6 left-1/2 -translate-x-1/2"
      >
        <motion.div
          animate={{ y: [0, 8, 0] }}
          transition={{ duration: 2, repeat: Infinity }}
          className="flex flex-col items-center gap-1.5"
        >
          <span className="text-[10px] uppercase font-sans tracking-widest text-muted-foreground/60">Scroll to view</span>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-brand-amber"
          >
            <path d="m6 9 6 6 6-6"/>
          </svg>
        </motion.div>
      </motion.div>
    </section>
  );
}
