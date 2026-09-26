#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /absolute/path/to/verified/artifacts" >&2
  exit 2
fi

source_dir=$1
region=${AWS_REGION:-us-east-1}
aws_bin=${AWS_BIN:-aws}
bucket=$("$aws_bin" cloudformation describe-stacks \
  --region "$region" \
  --stack-name ocp9 \
  --query "Stacks[0].Outputs[?OutputKey=='ArtifactBucketName'].OutputValue" \
  --output text)

manifest=$(mktemp /tmp/ocp9-artifact-manifest-XXXXXX)
trap 'rm -f "$manifest"' EXIT

cat >"$manifest" <<'EOF'
47f65aaf7cc3f7838a1d94b85c1895fc464f17397b7cbae53e67b78dd0592f7c  als_top100.npy
574001651639c6acc2806a07c977f7df4ae1e402adeb991aae56dbcc58b5b4bd  cf_i2i_top300.npy
d8087ddb58d284304252df2b45dca8c77d47417feb99dd89d84e84b1c84ff246  final_twotower_item_vec.npy
9080ac19b1e535efa4cec0e577c0ca3cef9e3e80fb22b4387e78db4c65ca433d  final_twotower_model.pth
b61fc80335f7b684c38e600685fa934aebf3c4f4fb62c5e4177f02554d8c2412  final_twotower_user_vec.npy
51a1ac716f9103680eb9be664471ee0eba8ec8a7430c625a23db5dd52a0e0f94  ground_truth.npy
623bd9981f92fc9aa49df2a3f4a6b8bf27bef7a1dc6a21d6d6acc558158c8359  gt_users.npy
d23da1a456196e6d0246dcbc501158bea7688a4bc9958e86cfdb2e00743fe897  last_click.npy
7f1b3679199536b45c1867f02b18ea9b05d6f331b7c1ac674542f668df4632a6  pop_list.npy
65f4f3279409282268f915caa9fb755c208f5d481065e181c40654b6db25a733  reranker.txt
8e8bd04e6db8745eea90e37fe4c6a3506cf7b9fcf5eb2e62d6a1b2f4ef3672b0  top_lists.pkl
225ee70299e92eafdee82e2f347602fafcc15cc3379e369462a71cc848233550  tt_top200.npy
59547c6babc35f732d1386ff8a83e493fa9fa3e0283f16a6235bf8bdcce0c978  valid_clicks.parquet
EOF

while read -r expected name; do
  path="$source_dir/$name"
  [[ -f "$path" ]] || { echo "Missing $path" >&2; exit 1; }
  actual=$(shasum -a 256 "$path" | awk '{print $1}')
  [[ "$actual" == "$expected" ]] || { echo "Hash mismatch for $name" >&2; exit 1; }
done <"$manifest"

while read -r expected name; do
  "$aws_bin" s3 cp \
    "$source_dir/$name" \
    "s3://$bucket/artifacts/$name" \
    --region "$region" \
    --only-show-errors \
    --metadata "sha256=$expected"
  echo "Uploaded $name"
done <"$manifest"

"$aws_bin" s3api list-objects-v2 \
  --bucket "$bucket" \
  --prefix artifacts/ \
  --region "$region" \
  --query '{count:KeyCount,bytes:sum(Contents[].Size)}' \
  --output json
