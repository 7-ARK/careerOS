import { motion } from 'motion/react';
import { ArrowRight, Lock } from 'lucide-react';

export function CTA() {
  return (
    <section className="px-6 py-24 md:py-32 relative overflow-hidden" id="cta-section">
      <div className="absolute inset-0 bg-background/25 -z-10" />
      
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-100px' }}
        transition={{ duration: 0.6 }}
        className="relative mx-auto max-w-4xl overflow-hidden rounded-3xl border border-border bg-card p-8 text-center md:p-16 shadow-2xl"
      >
        {/* Animated decorative circles */}
        <div className="absolute inset-0 -z-10 overflow-hidden pointer-events-none">
          <motion.div
            animate={{ 
              rotate: 360,
              scale: [1, 1.08, 1]
            }}
            transition={{ duration: 25, repeat: Infinity, ease: 'linear' }}
            className="absolute -right-32 -top-32 h-64 w-64 rounded-full border border-primary/10"
          />
          <motion.div
            animate={{ 
              rotate: -360,
              scale: [1.08, 1, 1.08]
            }}
            transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
            className="absolute -bottom-20 -left-20 h-48 w-48 rounded-full border border-brand-amber/10"
          />
          <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-brand-amber/5" />
        </div>

        <div className="relative z-10">
          <span className="inline-block mb-4 text-xs font-semibold uppercase tracking-widest text-brand-amber">
            Take Command
          </span>
          <h2 className="mb-4 font-serif text-3xl font-medium text-foreground sm:text-4xl md:text-5xl text-balance">
            Your career workflow engine is waiting.
          </h2>
          <p className="mx-auto mb-10 max-w-lg text-sm md:text-base text-muted-foreground leading-relaxed">
            Stop wasting hours copy-pasting resumes. Let careerOS match, rewrite, and draft 
            highly-compliant PDFs in real time while you direct your search.
          </p>

          <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
            <motion.a
              href="#analyze-job"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="group relative overflow-hidden rounded-full bg-primary px-8 py-4 text-base font-medium text-primary-foreground transition-all duration-300 shadow-lg shadow-primary/15"
            >
              <span className="relative z-10 flex items-center gap-2">
                Get started for free
                <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" />
              </span>
            </motion.a>
            
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-mono">
              <Lock className="size-3.5 text-brand-amber/70" />
              <span>Full privacy compliance. No card details required.</span>
            </div>
          </div>
        </div>
      </motion.div>
    </section>
  );
}
