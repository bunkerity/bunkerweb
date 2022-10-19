local cipher = {}

function cipher.new()
    return cipher
end

function cipher.encrypt(_, data, _, _)
    return data
end

function cipher.decrypt(_, data, _, _, _)
    return data
end

return cipher
