-- Give Pandoc pipe tables printable column widths instead of unbreakable l/r columns.
function Table(table)
  local count = #table.colspecs
  local widths
  if count == 2 then
    widths = {0.31, 0.69}
  elseif count == 4 then
    widths = {0.40, 0.20, 0.20, 0.20}
  else
    return table
  end

  for index, spec in ipairs(table.colspecs) do
    table.colspecs[index] = {spec[1], widths[index]}
  end
  return table
end

-- Leave enough room for the final claim boundary without making the UI screenshot unreadable.
function Image(image)
  if image.src:match("04%-naive%-gate%.png$") then
    image.attributes.width = "85%"
  end
  return image
end
