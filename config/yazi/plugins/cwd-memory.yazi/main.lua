local M = {}

function M:setup()
  ps.sub("cd", function()
    local cwd = tostring(cx.active.current.cwd)
    ya.async(function()
      fs.write(Url("D:/terminal-workbench/data/work-windows-yazi.cwd"), cwd)
    end)
  end)
end

return M
