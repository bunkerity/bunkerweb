export default function isReqKeys(reqArr: string[], obj: any) {
  for (let i = 0; i < reqArr.length; i++) {
    const key = reqArr[i];
    if (!(key in obj)) return false;
  }
  return true;
}
