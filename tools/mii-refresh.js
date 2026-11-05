// Pretendo LAN : régénère les images de Mii de tous les PNID depuis Mii Studio (Nintendo).
// À utiliser après des créations de PNID faites hors ligne (images génériques).
// Exécuté dans le conteneur « account » par : pretendo mii-refresh
const got = require('got');
const database = require('./dist/database');
const { PNID } = require('./dist/models/pnid');

(async () => {
	try {
		await got('https://studio.mii.nintendo.com/', { timeout: { request: 8000 }, retry: { limit: 0 }, throwHttpErrors: false });
	} catch (error) {
		console.error(`Mii Studio (Nintendo) injoignable : connexion Internet requise. Rien n'a été modifié. (${error.message})`);
		process.exit(2);
	}

	await database.connect();
	const pnids = await PNID.find({ deleted: { $ne: true }, 'mii.data': { $exists: true, $ne: '' } });
	let ok = 0;
	let failed = 0;
	for (const pnid of pnids) {
		try {
			await pnid.generateMiiImages();
			ok++;
			console.log(`  ${pnid.username} (${pnid.pid}) : OK`);
		} catch (error) {
			failed++;
			console.log(`  ${pnid.username} (${pnid.pid}) : échec (${error.message})`);
		}
	}
	console.log(`${ok} Mii régénéré(s), ${failed} échec(s)`);
	process.exit(failed ? 1 : 0);
})();
