function [T, audit] = preprocess_jsonl(filePath)
% MATLAB equivalent of the main log checks; not executed in this environment.
% Requires MATLAB R2020b or later. No absent bearing is replaced by zero.
arguments
    filePath (1,1) string
end
assert(isfile(filePath), 'Input file does not exist: %s', filePath);
lines = splitlines(fileread(filePath));
seen = containers.Map('KeyType','char','ValueType','char');
rows = cell(0,7);
audit = struct('accepted',0,'rejected',0,'duplicate',0,'structuralMissing',0);
lastTime = 0;
for k = 1:numel(lines)
    if strlength(strtrim(lines{k})) == 0, continue; end
    z = jsondecode(lines{k});
    id = char(z.request.request_id);
    fingerprint = [char(z.path), jsonencode(z.request)];
    if isKey(seen,id)
        assert(strcmp(seen(id),fingerprint), 'request_id conflict on row %d', k);
        audit.duplicate = audit.duplicate + 1;
        continue;
    end
    seen(id) = fingerprint;
    if ~z.response.accepted
        audit.rejected = audit.rejected + 1;
        continue; % Never replace lastTime with a rejected response's zero.
    end
    vt = z.response.virtual_time_s;
    assert(isfinite(vt) && vt >= lastTime-1e-6, 'Invalid clock on row %d', k);
    lastTime = vt;
    audit.accepted = audit.accepted + 1;
    x=NaN; y=NaN; ch=NaN; theta=NaN; kind="";
    if isfield(z.request,'position')
        x=z.request.position.x; y=z.request.position.y; ch=z.request.channel;
        assert(all(isfinite([x,y])) && all(abs([x,y])<=2e6));
        assert(ch>=1 && ch<=20 && ch==fix(ch));
    end
    if strcmp(z.path,'/measure')
        kind=string(z.response.measure_result);
        if kind=="direction"
            assert(isfield(z.response,'svd_deg'), 'Missing direction value');
            theta=z.response.svd_deg;
            assert(isfinite(theta) && theta>=0 && theta<360);
        else
            assert(kind=="near" || kind=="no_signal");
            audit.structuralMissing=audit.structuralMissing+1;
        end
    end
    rows(end+1,:)={string(z.path),x,y,ch,kind,theta,vt}; %#ok<AGROW>
end
T=cell2table(rows,'VariableNames',{'path','x','y','channel','measure_result','svd_deg','virtual_time_s'});
end
