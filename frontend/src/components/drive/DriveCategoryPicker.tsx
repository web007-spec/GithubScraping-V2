"use client";

import type { DriveCategory } from "@/lib/google-drive-types";

type Props = {
  categories: DriveCategory[];
  selected: string[];
  onChange: (next: string[]) => void;
};

function toggle(list: string[], id: string): string[] {
  return list.includes(id) ? list.filter((x) => x !== id) : [...list, id];
}

export default function DriveCategoryPicker({ categories, selected, onChange }: Props) {
  return (
    <div className="docs-crawl__categories">
      <h3>Content categories</h3>
      <p className="docs-crawl__hint">
        Only files matching your selection are downloaded from discovered public folders and documents.
      </p>
      <div className="drive-category-picker__grid">
        {categories.map((cat) => {
          const catChecked = selected.includes(cat.id);
          return (
            <fieldset key={cat.id} className="drive-category-picker__group card">
              <label className="drive-category-picker__main">
                <input
                  type="checkbox"
                  checked={catChecked}
                  onChange={() => onChange(toggle(selected, cat.id))}
                />
                <span>
                  <span className="drive-category-picker__label">{cat.label}</span>
                  <span className="drive-category-picker__desc">{cat.description}</span>
                </span>
              </label>
              {cat.subcategories?.length ? (
                <div className="drive-category-picker__subs">
                  {cat.subcategories.map((sub) => (
                    <label key={sub.id} className="drive-category-picker__sub">
                      <input
                        type="checkbox"
                        checked={selected.includes(sub.id)}
                        onChange={() => onChange(toggle(selected, sub.id))}
                      />
                      {sub.label}
                    </label>
                  ))}
                </div>
              ) : null}
            </fieldset>
          );
        })}
      </div>
    </div>
  );
}
