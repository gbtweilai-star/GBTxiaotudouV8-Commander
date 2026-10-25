# frozen_string_literal: true

# 负对照 · Ruby 侧（**只做行级判据**）

def export_all(rows)
  JSON.generate(rows)
rescue StandardError
end

def debug_here(payload)
  binding.pry
  payload
end
