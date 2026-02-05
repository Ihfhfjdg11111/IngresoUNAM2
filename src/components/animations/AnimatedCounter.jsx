import { useEffect, useRef, useState } from "react";
import { useInView, motion } from "framer-motion";

export const AnimatedCounter = ({ 
  value,
  end,
  duration = 2,
  suffix = "",
  prefix = "",
  className = ""
}) => {
  // Support both 'value' and 'end' props for backward compatibility
  const targetValue = value ?? end ?? 0;
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true });
  const hasAnimated = useRef(false);

  useEffect(() => {
    if (isInView && !hasAnimated.current) {
      hasAnimated.current = true;
      const startTime = Date.now();
      const endValue = Number(targetValue) || 0;

      const animate = () => {
        const now = Date.now();
        const progress = Math.min((now - startTime) / (duration * 1000), 1);
        
        // Easing function (ease-out)
        const easeOut = 1 - Math.pow(1 - progress, 3);
        
        setCount(Math.floor(easeOut * endValue));

        if (progress < 1) {
          requestAnimationFrame(animate);
        } else {
          setCount(endValue);
        }
      };

      requestAnimationFrame(animate);
    }
  }, [isInView, targetValue, duration]);

  return (
    <motion.span
      ref={ref}
      className={className}
      initial={{ opacity: 0, scale: 0.5 }}
      animate={isInView ? { opacity: 1, scale: 1 } : {}}
      transition={{ duration: 0.5 }}
    >
      {prefix}{(count ?? 0).toLocaleString()}{suffix}
    </motion.span>
  );
};
