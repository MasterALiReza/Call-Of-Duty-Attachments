import React, {
  useState,
  useRef,
  useEffect,
  useCallback,
  useId,
  ReactNode,
} from 'react';
import { ChevronDown, Check, Search, X } from 'lucide-react';

export interface SelectOption<T = string | number> {
  value: T;
  label: string;
  sublabel?: string;
  icon?: ReactNode;
  badge?: ReactNode;
  disabled?: boolean;
}

export interface SelectProps<T = string | number> {
  options: SelectOption<T>[];
  value?: T;
  defaultValue?: T;
  onChange: (value: T) => void;
  placeholder?: string;
  label?: string;
  error?: string;
  helperText?: string;
  disabled?: boolean;
  searchable?: boolean;
  searchPlaceholder?: string;
  clearable?: boolean;
  icon?: ReactNode;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'filled' | 'pill';
  className?: string;
  dropdownClassName?: string;
  required?: boolean;
  name?: string;
}

export function Select<T extends string | number = string | number>({
  options,
  value,
  defaultValue,
  onChange,
  placeholder = 'انتخاب کنید...',
  label,
  error,
  helperText,
  disabled = false,
  searchable = false,
  searchPlaceholder = 'جستجو...',
  clearable = false,
  icon,
  size = 'md',
  variant = 'default',
  className = '',
  dropdownClassName = '',
  required = false,
  name,
}: SelectProps<T>) {
  const [isOpen, setIsOpen] = useState(false);
  const [internalValue, setInternalValue] = useState<T | undefined>(
    value !== undefined ? value : defaultValue
  );
  const [searchQuery, setSearchQuery] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState<number>(-1);
  const [dropUpward, setDropUpward] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listboxRef = useRef<HTMLUListElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const id = useId();

  useEffect(() => {
    if (value !== undefined) {
      setInternalValue(value);
    }
  }, [value]);

  const selectedOption = options.find((opt) => opt.value === internalValue);

  const filteredOptions = searchable
    ? options.filter(
        (opt) =>
          opt.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
          (opt.sublabel &&
            opt.sublabel.toLowerCase().includes(searchQuery.toLowerCase()))
      )
    : options;

  const calculatePosition = useCallback(() => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    const expectedHeight = 240;
    setDropUpward(spaceBelow < expectedHeight && rect.top > expectedHeight);
  }, []);

  const openDropdown = () => {
    if (disabled) return;
    calculatePosition();
    setIsOpen(true);
    setSearchQuery('');
    const curIdx = filteredOptions.findIndex((opt) => opt.value === internalValue);
    setHighlightedIndex(curIdx >= 0 ? curIdx : 0);
  };

  const closeDropdown = () => {
    setIsOpen(false);
    setSearchQuery('');
    setHighlightedIndex(-1);
    triggerRef.current?.focus();
  };

  const handleSelect = (val: T) => {
    setInternalValue(val);
    onChange(val);
    closeDropdown();
  };

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent | TouchEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('touchstart', handleClickOutside);
      window.addEventListener('resize', calculatePosition);
      window.addEventListener('scroll', calculatePosition, true);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside);
      window.removeEventListener('resize', calculatePosition);
      window.removeEventListener('scroll', calculatePosition, true);
    };
  }, [isOpen, calculatePosition]);

  useEffect(() => {
    if (isOpen && searchable && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [isOpen, searchable]);

  useEffect(() => {
    if (isOpen && listboxRef.current && highlightedIndex >= 0) {
      const activeEl = listboxRef.current.children[
        highlightedIndex
      ] as HTMLElement;
      if (activeEl) {
        activeEl.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [highlightedIndex, isOpen]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (disabled) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        if (!isOpen) {
          openDropdown();
        } else {
          setHighlightedIndex((prev) =>
            prev < filteredOptions.length - 1 ? prev + 1 : 0
          );
        }
        break;

      case 'ArrowUp':
        e.preventDefault();
        if (!isOpen) {
          openDropdown();
        } else {
          setHighlightedIndex((prev) =>
            prev > 0 ? prev - 1 : filteredOptions.length - 1
          );
        }
        break;

      case 'Enter':
      case ' ':
        if (!isOpen) {
          e.preventDefault();
          openDropdown();
        } else if (highlightedIndex >= 0 && filteredOptions[highlightedIndex]) {
          e.preventDefault();
          if (!filteredOptions[highlightedIndex].disabled) {
            handleSelect(filteredOptions[highlightedIndex].value);
          }
        }
        break;

      case 'Escape':
        if (isOpen) {
          e.preventDefault();
          closeDropdown();
        }
        break;

      case 'Tab':
        if (isOpen) {
          setIsOpen(false);
        }
        break;

      case 'Home':
        if (isOpen) {
          e.preventDefault();
          setHighlightedIndex(0);
        }
        break;

      case 'End':
        if (isOpen) {
          e.preventDefault();
          setHighlightedIndex(filteredOptions.length - 1);
        }
        break;
    }
  };

  const sizeStyles = {
    sm: 'text-[11px] py-1 px-3 min-h-[34px] rounded-xl',
    md: 'text-xs py-2 px-3.5 min-h-[40px] rounded-xl',
    lg: 'text-sm py-2.5 px-4 min-h-[46px] rounded-2xl',
  };

  const variantStyles = {
    default:
      'bg-card border-border hover:border-border-highlight/60 focus:border-primary',
    filled:
      'bg-card-surface border-border-subtle hover:border-border-highlight/60 focus:border-primary',
    pill: 'bg-card border-border hover:border-primary focus:border-primary rounded-full px-4',
  };

  return (
    <div
      className={`relative flex flex-col gap-1 w-full text-right ${className}`}
      ref={containerRef}
    >
      {label && (
        <label
          id={`${id}-label`}
          htmlFor={`${id}-trigger`}
          className="text-xs font-semibold text-mainText-muted select-none flex items-center justify-between"
        >
          <span>
            {label} {required && <span className="text-rose-500">*</span>}
          </span>
        </label>
      )}

      {name && (
        <input
          type="hidden"
          name={name}
          value={internalValue !== undefined ? String(internalValue) : ''}
        />
      )}

      <button
        type="button"
        id={`${id}-trigger`}
        ref={triggerRef}
        onClick={() => (isOpen ? closeDropdown() : openDropdown())}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-labelledby={label ? `${id}-label ${id}-trigger` : undefined}
        aria-controls={`${id}-listbox`}
        className={`w-full flex items-center justify-between gap-2 border transition-all duration-200 outline-none text-mainText shadow-sm ${
          sizeStyles[size]
        } ${variantStyles[variant]} ${
          isOpen ? 'border-primary ring-2 ring-primary/20 shadow-glow-primary' : ''
        } ${error ? 'border-rose-500/80 ring-1 ring-rose-500/30' : ''} ${
          disabled
            ? 'opacity-50 cursor-not-allowed bg-card-surface/40'
            : 'cursor-pointer'
        }`}
      >
        <div className="flex items-center gap-2 truncate flex-1 min-w-0">
          {icon && (
            <span className="text-mainText-muted flex-shrink-0 flex items-center">
              {icon}
            </span>
          )}

          {selectedOption ? (
            <span className="flex items-center gap-2 truncate font-bold">
              {selectedOption.icon && (
                <span className="flex-shrink-0">{selectedOption.icon}</span>
              )}
              <span className="truncate">{selectedOption.label}</span>
              {selectedOption.sublabel && (
                <span className="text-[10px] text-mainText-subtle font-normal truncate">
                  ({selectedOption.sublabel})
                </span>
              )}
            </span>
          ) : (
            <span className="text-mainText-muted/70 truncate font-medium">
              {placeholder}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5 flex-shrink-0 text-mainText-muted">
          {clearable && selectedOption && !disabled && (
            <span
              role="button"
              tabIndex={0}
              onClick={(e) => {
                e.stopPropagation();
                setInternalValue(undefined);
                onChange(undefined as any);
              }}
              className="p-0.5 rounded-full hover:bg-card-surface hover:text-mainText transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </span>
          )}
          <ChevronDown
            className={`w-4 h-4 transition-transform duration-200 ease-out ${
              isOpen ? 'rotate-180 text-primary' : 'text-mainText-subtle'
            }`}
          />
        </div>
      </button>

      {isOpen && (
        <div
          className={`absolute left-0 right-0 z-50 glass-panel rounded-2xl shadow-card-elevated border border-border overflow-hidden animate-in fade-in zoom-in-95 duration-150 ${
            dropUpward ? 'bottom-full mb-1.5' : 'top-full mt-1.5'
          } ${dropdownClassName}`}
        >
          {searchable && (
            <div className="p-2 border-b border-border bg-card-surface/50 flex items-center gap-2">
              <Search className="w-3.5 h-3.5 text-mainText-subtle flex-shrink-0" />
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setHighlightedIndex(0);
                }}
                onKeyDown={handleKeyDown}
                placeholder={searchPlaceholder}
                className="w-full bg-transparent text-xs text-mainText placeholder:text-mainText-muted/60 focus:outline-none font-sans"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="text-mainText-subtle hover:text-mainText p-0.5"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>
          )}

          <ul
            id={`${id}-listbox`}
            ref={listboxRef}
            role="listbox"
            tabIndex={-1}
            aria-activedescendant={
              highlightedIndex >= 0 ? `${id}-opt-${highlightedIndex}` : undefined
            }
            className="max-h-56 overflow-y-auto p-1.5 space-y-0.5 divide-y-0 scrollbar-none"
          >
            {filteredOptions.length === 0 ? (
              <li className="px-3 py-4 text-center text-xs text-mainText-muted font-medium">
                موردی یافت نشد
              </li>
            ) : (
              filteredOptions.map((opt, idx) => {
                const isSelected = opt.value === internalValue;
                const isHighlighted = idx === highlightedIndex;

                return (
                  <li
                    key={String(opt.value)}
                    id={`${id}-opt-${idx}`}
                    role="option"
                    aria-selected={isSelected}
                    aria-disabled={opt.disabled}
                    onClick={() => {
                      if (!opt.disabled) handleSelect(opt.value);
                    }}
                    onMouseEnter={() => {
                      if (!opt.disabled) setHighlightedIndex(idx);
                    }}
                    className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs transition-colors duration-150 cursor-pointer ${
                      opt.disabled
                        ? 'opacity-40 cursor-not-allowed text-mainText-subtle'
                        : isSelected
                        ? 'bg-primary/15 text-primary font-bold shadow-sm'
                        : isHighlighted
                        ? 'bg-card-hover text-mainText'
                        : 'text-mainText hover:bg-card-hover'
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate min-w-0 flex-1">
                      {opt.icon && (
                        <span className="flex-shrink-0">{opt.icon}</span>
                      )}
                      <span className="truncate font-semibold">{opt.label}</span>
                      {opt.sublabel && (
                        <span className="text-[10px] text-mainText-subtle font-normal truncate">
                          ({opt.sublabel})
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2 flex-shrink-0">
                      {opt.badge && <span>{opt.badge}</span>}
                      {isSelected && (
                        <Check className="w-3.5 h-3.5 text-primary animate-in zoom-in-75 duration-100" />
                      )}
                    </div>
                  </li>
                );
              })
            )}
          </ul>
        </div>
      )}

      {error && (
        <span className="text-[11px] text-rose-500 font-medium">{error}</span>
      )}
      {!error && helperText && (
        <span className="text-[11px] text-mainText-subtle">{helperText}</span>
      )}
    </div>
  );
}
